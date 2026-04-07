"""
Expo Push Notification service.

Sends multilingual (Hinglish/Tanglish/Teluglish/etc.) scheduled
notifications and refund alerts using Expo's push API.
"""
import random
import logging
import requests
from django.db import models as djmodels

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'

# ─────────────────────────────────────────────────────────────────────────────
# Message banks per time slot × language
# Language keys match Profile.language values: ta, hi, te, en, ml, gu, bn
# ─────────────────────────────────────────────────────────────────────────────

MESSAGES = {
    9: {  # 9 AM
        'hi': [
            "Good morning ☀️\nYaar, friends wait kar rahe hain… aa jao 😊",
            "Rise and shine 😄\nAaj kis se baat karoge?",
            "Good morning yaar 😊\nKoi tere liye wait kar raha hai today…",
            "Naya din, naye chats ☀️\nAa mil kisi interesting se 😉",
            "Subah ho gayi bhai 😄\nChal ek quick chat maar lo!",
        ],
        'ta': [
            "Good morning ☀️\nUngal friends online irukaanga… join pannalama? 😊",
            "Kaalai vanakkam da ☀️\nYaaru kitta pesaporeenga inniki?",
            "Morning da 😄\nSomeone waiting for you… varuveenga illaya?",
            "New day new chats ☀️\nInteresting people wait panraanga 😉",
            "Coffee time ah? ☕\nChal oru short chat pannalama!",
        ],
        'te': [
            "Good morning ☀️\nMee friends wait chestunaaru… join avvandi 😊",
            "Subbanam ra 😄\nEedu matladutaavu inniki?",
            "Morning vibes ☀️\nOkadu mee kosam wait chestunaadu…",
            "Kotta roju kotta chats ☀️\nInteresting ga untundhi 😉",
            "Levandi ra 😄\nOkka quick chat cheseyandi!",
        ],
        'en': [
            "Good morning ☀️\nYour friends are waiting for you… come say hi 😊",
            "Rise and shine 😄\nWho are you gonna chat with today?",
            "Good morning! 😊\nSomeone might be waiting to talk to you today…",
            "New day new chats ☀️\nCome meet someone interesting today 😉",
            "Morning! ☀️\nJump in and start a conversation!",
        ],
        'ml': [
            "Suprabhaatham ☀️\nNinte friends wait cheyyunnu… varunno? 😊",
            "Good morning da 😄\nInnu aara koode samsarikum?",
            "Puthiya divasam ☀️\nPuthiya friendsine kandam 😉",
            "Chaya kudikkaamo? ☕\nOru quick chat aakaam!",
            "Morning ☀️\nKoode oru nalla vaakkathinte kootukaar undallo 😊",
        ],
        'gu': [
            "Suprabhat ☀️\nTara friends wait kare che… aa jaa 😊",
            "Good morning yaar 😄\nAaj koi sathe vaat karishun?",
            "Navoo din ☀️\nNava mitra banaaviye 😉",
            "Chaay time? ☕\nEk chat maari naakho!",
            "Uthvo ane avo ☀️\nFriends tane yaad kare che 😊",
        ],
        'bn': [
            "Suprobhat ☀️\nTomar bondhurao wait korche… esho 😊",
            "Good morning 😄\nAaj ke ke ke sathe kotha bolbe?",
            "Notun din ☀️\nNaye bondhu bano ajo 😉",
            "Cha khaccho? ☕\nEktu chat kore nao!",
            "Utho ar esho ☀️\nSবাই tomar jonyo wait korche 😊",
        ],
    },
    13: {  # 1 PM
        'hi': [
            "Hi 👋\nFree ho? Koi baat karna chahta hai…",
            "Lunch time ho gaya? 😄\nKisi naye se baat kyu nahi karte?",
            "Heyy 😊\nThoda break lo… chal chat karo friends ke saath",
            "Afternoon vibes ☀️\nShayad koi special wait kar raha hai 😉",
            "Ek message se great conversation shuru ho sakti hai 💬",
        ],
        'ta': [
            "Hi 👋\nFree aa irukiya? Someone wants to talk…",
            "Lunch time aa? 😄\nEn nee someone new kitta pesala?",
            "Heyy 😊\nThoda break edukko… friends kitta chat pannalama",
            "Afternoon vibes ☀️\nSomeone special wait panraranga 😉",
            "Oru message pothum… great conversation start aagum 💬",
        ],
        'te': [
            "Hi 👋\nFree gaa unnava? Okadu matladaalanukunnaadu…",
            "Lunch ayyinda? 😄\nKotta person tho matladakoodadu aa?",
            "Heyy 😊\nKoncham break teesko… friends tho chat cheseyandi",
            "Afternoon vibes ☀️\nSpecial okadu wait chestunaadu 😉",
            "Oka message chaalu… great conversation start avutundi 💬",
        ],
        'en': [
            "Hi 👋\nFree right now? Someone wants to talk…",
            "Lunch time? 😄\nWhy not chat with someone new?",
            "Heyy 😊\nTake a lil break… come chill with friends",
            "Afternoon vibes ☀️\nMaybe someone special is waiting for you 😉",
            "Hi there 👋\nOne message can start a great conversation 💬",
        ],
        'ml': [
            "Hi 👋\nFree aano? Okkar samsarikkaan undelu…",
            "Uchakali aayo? 😄\nPudhiya aarumaayitum samsarichukkoode?",
            "Heyy 😊\nOru break edukku… friends kkoode chat aakaam",
            "Ucha vibes ☀️\nSpecial okkar wait cheyyunnu 😉",
            "Oru message matham... great conversation shuruvaakunnu 💬",
        ],
        'gu': [
            "Hi 👋\nFree cho? Koi vaat karva manghe che…",
            "Lunch time? 😄\nNava mitra sathe vaat karo ne?",
            "Heyy 😊\nEk break lo… friends sathe chat karo",
            "Dupahar vibes ☀️\nKoi special wait kare che 😉",
            "Ek message si sharu thay... great vaartalaap 💬",
        ],
        'bn': [
            "Hi 👋\nFree acho? Keu kotha bolte chay…",
            "Dupur hoye gelo? 😄\nNye karo sathe kotha bolbena?",
            "Heyy 😊\nEktu break nao… bondhuder saathe chat koro",
            "Dupur vibes ☀️\nSpecial keu wait korche 😉",
            "Ekta message-e shuru hoy... onek boro golpo 💬",
        ],
    },
    18: {  # 6 PM
        'hi': [
            "Good evening 🌆\nThaka hua lagta hai… ek fun chat try karo 😉",
            "Evening time 😄\nFriends online hain… join karo",
            "Lamba din tha? 😌\nAa chill karo ek aachi baat ke saath",
            "Heyy 👋\nTere friends abhi online hain",
            "Evening chill 🌇\nAaj ek naya friend kyun nahi banate?",
        ],
        'ta': [
            "Good evening 🌆\nThaka maari irukiya? Fun chat fix panni viduvom 😉",
            "Evening time 😄\nFriends online irukaanga… join pannalama?",
            "Naal mudichutu iruka? 😌\nNalla pesalama relax panniko",
            "Heyy 👋\nUngal friends ippo online",
            "Evening chill 🌇\nInniki oru pudhiya friend pannikalam 😉",
        ],
        'te': [
            "Good evening 🌆\nAlasipoynava? Fun chat try cheseyandi 😉",
            "Evening time 😄\nFriends online unnaru… join avvandi",
            "Peddga roju ayyinda? 😌\nOka machi conversation tho relax avvandi",
            "Heyy 👋\nMee friends ippudu online ga unnaru",
            "Evening chill 🌇\nIvvala kotta friend cheskovadam em antaaru? 😉",
        ],
        'en': [
            "Good evening 🌆\nYou look tired… maybe a fun chat can fix it 😉",
            "Evening time 😄\nFriends are online… come join!",
            "Long day? 😌\nCome relax with a nice conversation",
            "Heyy 👋\nYour friends are online right now",
            "Evening chill time 🌇\nWhy not make a new friend today? 😉",
        ],
        'ml': [
            "Good evening 🌆\nMandi aano? Oru fun chat fix cheyyaam 😉",
            "Evening aayo 😄\nFriends online unnallo… varunno?",
            "Valiya divasam aayirunnoo? 😌\nNalla samsarichhu relax aakaam",
            "Heyy 👋\nNinte friends ippol online aayi",
            "Evening chill 🌇\nInnale oru puthiya bondhu undaakkuka 😉",
        ],
        'gu': [
            "Good evening 🌆\nThaki gayi? Ek fun chat try karo 😉",
            "Evening time 😄\nFriends online che… join karo",
            "Laambo din? 😌\nSaaraa vaat sathe relax karo",
            "Heyy 👋\nTara friends hun online che",
            "Evening chill 🌇\nAaj ek navo mitra banaavo 😉",
        ],
        'bn': [
            "Good evening 🌆\nThakcho? Ektu fun chat koro 😉",
            "Evening time 😄\nBondhurao online ache… join korona",
            "Lamba din? 😌\nEktu relax koro kotha boleye",
            "Heyy 👋\nTomar bondhurao ekhon online",
            "Evening chill 🌇\nAjo ekta noya bondhu banao 😉",
        ],
    },
    22: {  # 10 PM
        'hi': [
            "Late night 🌙\nAkela feel ho raha hai? Yahan hoon main",
            "Night vibes 😌\nKoi tumse baat karna chahta hai",
            "Sone se pehle 😴\nEk last conversation?",
            "Raat ka mahaul 🌙\nYaar friends still jaag rahe hain",
            "Good night mood 🌙\nChal chill karo kisi ke saath",
        ],
        'ta': [
            "Late night 🌙\nOruthan a irukkiya? Inga iruken",
            "Night vibes 😌\nYaaro unna pesa wait panraanga",
            "Thoongum munna 😴\nOru last conversation?",
            "Iravu time 🌙\nFriends innum jaakkaama irukaanga",
            "Good night mood 🌙\nYaaravadu kitta chill pannikalam",
        ],
        'te': [
            "Late night 🌙\nOkkadiga feel avutunnava? Ikkade unnanu",
            "Night vibes 😌\nOkadu nee tho matladaali ani wait chestunaadu",
            "Padukkodam mundu 😴\nOka last conversation cheseddam?",
            "Raatri time 🌙\nFriends inka maelukonnaru",
            "Good night mood 🌙\nOkari tho chill cheseyandi",
        ],
        'en': [
            "Late night 🌙\nFeeling lonely? I'm here for you",
            "Night vibes 😌\nSomeone might want to talk with you",
            "Before sleep 😴\nOne last conversation?",
            "Hey night owl 🦉\nYour friends are still awake",
            "Good night mood 🌙\nCome chill and talk with someone",
        ],
        'ml': [
            "Late night 🌙\nOkkaney aano? Ikkade undu",
            "Night vibes 😌\nOkkar ninte kkoode samsarikkaan ready",
            "Urangunnad muŋpe 😴\nOru last conversation?",
            "Raatri time 🌙\nFriends ingunum unarnnirikkunnunde",
            "Good night mood 🌙\nOru nalla vaakkathinu varunno?",
        ],
        'gu': [
            "Late night 🌙\nEkla feel thao cho? Huu ahu chu",
            "Night vibes 😌\nKoi tamari sathe vaat karva manga che",
            "Suvaani aagal 😴\nEk last vaat?",
            "Raat no time 🌙\nFriends hun jaage che",
            "Good night mood 🌙\nKoi sathe chill karo",
        ],
        'bn': [
            "Late night 🌙\nEkla lagche? Ami achi",
            "Night vibes 😌\nKeu tomaar saathe kotha bolte chay",
            "Ghumobar age 😴\nEkta last golpo?",
            "Raat er mood 🌙\nBondhura ekhono jaage",
            "Good night mood 🌙\nKaro saathe chill koro",
        ],
    },
}

# Fallback language → use 'en'
def _get_messages(lang: str, hour: int) -> list[str]:
    slot = MESSAGES.get(hour, MESSAGES[9])
    return slot.get(lang, slot.get('en', ['Hey! Come chat with someone today 😊']))


def _get_user_tokens(user_id: int) -> list[str]:
    """Helper to get all valid tokens for a user from both PushToken and Profile models."""
    from api.models import PushToken, Profile
    tokens = set(PushToken.objects.filter(user_id=user_id).values_list('expo_token', flat=True))
    try:
        profile = Profile.objects.get(user_id=user_id)
        if profile.device_token and profile.device_token.startswith('ExponentPushToken'):
            tokens.add(profile.device_token)
    except Profile.DoesNotExist:
        pass
    return list(tokens)

def send_push_notification(tokens: list[str], title: str, body: str, data: dict = None) -> dict:
    """Send push notifications to a list of Expo tokens via Expo's API."""
    if not tokens:
        return {'sent': 0, 'errors': 0}

    messages = []
    for token in tokens:
        msg = {
            'to': token,
            'sound': 'default',
            'title': title,
            'body': body,
            'priority': 'normal',
        }
        if data:
            msg['data'] = data
        messages.append(msg)

    sent = 0
    errors = 0
    # Expo allows max 100 messages per request
    chunk_size = 100
    for i in range(0, len(messages), chunk_size):
        chunk = messages[i:i + chunk_size]
        try:
            resp = requests.post(
                EXPO_PUSH_URL,
                json=chunk,
                headers={
                    'Accept': 'application/json',
                    'Accept-encoding': 'gzip, deflate',
                    'Content-Type': 'application/json',
                },
                timeout=15,
            )
            resp.raise_for_status()
            data_resp = resp.json().get('data', [])
            for item in data_resp:
                if item.get('status') == 'ok':
                    sent += 1
                else:
                    errors += 1
                    logger.warning('Expo push error: %s', item)
        except Exception as exc:
            logger.error('Failed to send push batch: %s', exc)
            errors += len(chunk)

    return {'sent': sent, 'errors': errors}


def send_scheduled_push(hour: int) -> dict:
    """
    Send scheduled emotional push notifications.
    hour should be one of: 9, 13, 18, 22
    Only sends to users with notifications_enabled=True.
    """
    from api.models import PushToken, UserSetting, Profile

    # Get push tokens for users who have notifications enabled
    enabled_user_ids = UserSetting.objects.filter(
        notifications_enabled=True
    ).values_list('user_id', flat=True)

    # Group user IDs by language
    lang_user_ids: dict[str, list[int]] = {}
    profiles = Profile.objects.filter(user_id__in=enabled_user_ids).values('user_id', 'language')

    for p in profiles:
        lang = p.get('language') or 'en'
        lang_user_ids.setdefault(lang, []).append(p['user_id'])

    total_sent = 0
    total_errors = 0

    for lang, user_ids in lang_user_ids.items():
        # Get all tokens for these users
        all_tokens = []
        for uid in user_ids:
            all_tokens.extend(_get_user_tokens(uid))
        
        if not all_tokens:
            continue

        msgs = _get_messages(lang, hour)
        body = random.choice(msgs)
        result = send_push_notification(all_tokens, title='', body=body)
        total_sent += result['sent']
        total_errors += result['errors']
        logger.info('Sent %d notifications for lang=%s hour=%s', result['sent'], lang, hour)

    return {'sent': total_sent, 'errors': total_errors, 'hour': hour}


def send_refund_notification(user_id: int) -> dict:
    """
    Send a push notification to a user when their call coins are refunded.
    Language-aware: picks the right message style based on user's language.
    """
    from api.models import PushToken, Profile

    REFUND_MESSAGES = {
        'hi': "Call connect nahi hua 😔\nTension mat lo… coins refund ho gaya! 💰",
        'ta': "Call connect aagala 😔\nWorry pannaathe… coins refund pannitom! 💰",
        'te': "Call connect kaaledu 😔\nWorry cheyyaakandi… coins refund chesaamu! 💰",
        'en': "Call didn't connect 😔\nDon't worry… your coins have been refunded! 💰",
        'ml': "Call connect aayilla 😔\nVishashikkanda… coins refund chessu! 💰",
        'gu': "Call connect na thayo 😔\nChinta na karo… coins paacha aapi didha! 💰",
        'bn': "Call connect hoyni 😔\nChinta koro na… coins refund hoeche! 💰",
    }

    try:
        profile = Profile.objects.get(user_id=user_id)
        lang = profile.language or 'en'
    except Profile.DoesNotExist:
        lang = 'en'

    message = REFUND_MESSAGES.get(lang, REFUND_MESSAGES['en'])
    tokens = _get_user_tokens(user_id)

    if not tokens:
        return {'sent': 0, 'errors': 0}

    return send_push_notification(tokens, title='', body=message, data={'type': 'refund'})
def send_call_push_notification(caller_name: str, callee_id: int, session_id: int, call_type: str) -> dict:
    """
    Send a push notification for an incoming call.
    """
    CALL_MESSAGES = {
        'hi': f"{caller_name} aapko call kar rahe hain… 📞",
        'ta': f"{caller_name} ungalukku call panraaru… 📞",
        'te': f"{caller_name} mee kosam call chestunaaru… 📞",
        'en': f"{caller_name} is calling you… 📞",
        'ml': f"{caller_name} ninne call cheyyunnu… 📞",
        'gu': f"{caller_name} tane call kare che… 📞",
        'bn': f"{caller_name} tomake call korche… 📞",
    }

    try:
        from api.models import Profile
        profile = Profile.objects.get(user_id=callee_id)
        lang = profile.language or 'en'
    except Exception:
        lang = 'en'

    message = CALL_MESSAGES.get(lang, CALL_MESSAGES['en'])
    tokens = _get_user_tokens(callee_id)

    if not tokens:
        return {'sent': 0, 'errors': 0}

    # High priority for calls
    data = {
        'type': 'incoming-call',
        'sessionId': session_id,
        'callerName': caller_name,
        'callType': call_type,
    }

    messages = []
    for token in tokens:
        messages.append({
            'to': token,
            'sound': 'default',
            'title': 'Incoming Call 📞',
            'body': message,
            'priority': 'high',
            '_displayInForeground': True,
            'data': data,
            'channelId': 'incoming-calls',  # Android notification channel
        })

    if not messages:
        return {'sent': 0, 'errors': 0}

    import requests as _req
    try:
        resp = _req.post(
            EXPO_PUSH_URL,
            json=messages,
            headers={
                'Accept': 'application/json',
                'Accept-encoding': 'gzip, deflate',
                'Content-Type': 'application/json',
            },
            timeout=15,
        )
        resp.raise_for_status()
        data_resp = resp.json().get('data', [])
        sent = sum(1 for item in data_resp if item.get('status') == 'ok')
        errors = len(data_resp) - sent
        return {'sent': sent, 'errors': errors}
    except Exception as exc:
        logger.error('Failed to send call push: %s', exc)
        return {'sent': 0, 'errors': len(messages)}
