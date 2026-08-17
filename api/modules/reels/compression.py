import os
import subprocess
import tempfile
import logging
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

# Size limit in bytes (50 MB)
REEL_VIDEO_SIZE_LIMIT = 50 * 1024 * 1024

def _is_ffmpeg_available() -> bool:
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def _run_ffmpeg_encode(file_obj, crf=18, preset='medium') -> bytes:
    """
    Re-encodes a video using FFmpeg to HEVC (H.265) at the given CRF and preset.
    Returns the compressed bytes or None if it fails.
    """
    tmp_in = None
    tmp_out = None
    try:
        suffix_in = os.path.splitext(getattr(file_obj, 'name', 'video.mp4'))[1] or '.mp4'
        tmp_in = tempfile.NamedTemporaryFile(suffix=suffix_in, delete=False)
        tmp_out = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)

        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        tmp_in.write(file_obj.read())
        tmp_in.flush()
        tmp_in.close()
        tmp_out.close()

        cmd = [
            'ffmpeg', '-y',
            '-i', tmp_in.name,
            '-c:v', 'libx265',
            '-crf', str(crf),
            '-preset', preset,
            '-c:a', 'copy',
            '-movflags', '+faststart',
            tmp_out.name
        ]

        logger.info(f"[ReelsCompress] Running FFmpeg HEVC encode (CRF {crf}): {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, timeout=300)

        if result.returncode != 0:
            logger.error(f"[ReelsCompress] FFmpeg error (CRF {crf}): {result.stderr.decode()}")
            return None

        with open(tmp_out.name, 'rb') as f:
            return f.read()

    except subprocess.TimeoutExpired:
        logger.error(f"[ReelsCompress] FFmpeg timed out for CRF {crf}.")
        return None
    except Exception as e:
        logger.error(f"[ReelsCompress] FFmpeg encode failed: {e}")
        return None
    finally:
        for tmp in [tmp_in, tmp_out]:
            if tmp and os.path.exists(tmp.name):
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass

def compress_reel_video(file_obj):
    """
    Compresses a reel video if it exceeds the 50MB limit.
    Uses a two-tier approach to ensure it fits under the limit without visible quality loss.
    Returns:
        (ContentFile, bool): The processed file object and a boolean indicating if compression was applied.
    """
    size = file_obj.size
    
    if size <= REEL_VIDEO_SIZE_LIMIT:
        return file_obj, False

    if not _is_ffmpeg_available():
        logger.warning("[ReelsCompress] FFmpeg not installed. Skipping compression.")
        return file_obj, False

    logger.info(f"[ReelsCompress] Video {size/1024/1024:.2f}MB > 50MB. Starting Phase 1 (CRF 18)...")
    
    # Phase 1: Visually lossless compression (CRF 18)
    compressed_bytes_1 = _run_ffmpeg_encode(file_obj, crf=18, preset='medium')
    
    if compressed_bytes_1:
        c1_size = len(compressed_bytes_1)
        if c1_size <= REEL_VIDEO_SIZE_LIMIT:
            logger.info(f"[ReelsCompress] Phase 1 success: {c1_size/1024/1024:.2f}MB")
            return ContentFile(compressed_bytes_1), True
            
        logger.info(f"[ReelsCompress] Phase 1 resulted in {c1_size/1024/1024:.2f}MB, still > 50MB. Starting Phase 2 (CRF 24, slower)...")
        
        # Phase 2: Aggressive compression (CRF 24, slower preset) - still excellent quality but smaller
        compressed_bytes_2 = _run_ffmpeg_encode(file_obj, crf=24, preset='slower')
        
        if compressed_bytes_2:
            c2_size = len(compressed_bytes_2)
            logger.info(f"[ReelsCompress] Phase 2 finished: {c2_size/1024/1024:.2f}MB")
            
            # If Phase 2 is smaller than Phase 1, use Phase 2, even if it's still > 50MB
            if c2_size < c1_size:
                return ContentFile(compressed_bytes_2), True
        
        # Fallback to Phase 1 if Phase 2 failed or somehow produced a larger file
        if c1_size < size:
            return ContentFile(compressed_bytes_1), True

    # If all compression attempts failed or produced larger files, return original
    if hasattr(file_obj, 'seek'):
        file_obj.seek(0)
    return file_obj, False
