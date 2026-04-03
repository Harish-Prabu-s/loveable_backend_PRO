# Vibely Backend - PyCharm Setup

This folder contains the Django backend for the Vibely app. You can move this folder to a new location and open it independently in PyCharm.

## How to Open in PyCharm

1.  **Open Project**:
    *   Launch PyCharm.
    *   Select **Open** and choose this `backend` folder.

2.  **Configure Interpreter**:
    *   Go to **Settings/Preferences** > **Project: backend** > **Python Interpreter**.
    *   Click **Add Interpreter** > **Add Local Interpreter**.
    *   Select **Virtual Environment**:
        *   **New**: Check "New environment" to create a fresh one (recommended).
        *   **Location**: PyCharm usually suggests a `venv` folder inside the project.
        *   **Base interpreter**: Select your Python 3.10+ executable.
    *   Click **OK**.

3.  **Install Dependencies**:
    *   Open the `requirements.txt` file in PyCharm.
    *   PyCharm should show a banner asking to install requirements. Click **Install requirements**.
    *   *Alternatively*, open the **Terminal** tab (Alt+F12) and run:
        ```bash
        pip install -r requirements.txt
        ```

4.  **Run the Server**:
    *   Open `manage.py`.
    *   Right-click anywhere in the editor and select **Run 'manage'**.
    *   *Note*: This might just run the script. To run the *server*, you need to edit the configuration:
        *   Click the Run Configuration dropdown (top right) > **Edit Configurations**.
        *   In **Parameters**, add: `runserver`.
        *   Click **OK** and run it again.
    *   *Alternatively*, use the **Terminal**:
        ```bash
        python manage.py runserver
        ```

## Key Files
*   `manage.py`: Django command-line utility.
*   `vibely_backend/settings.py`: Main configuration (Database, Apps, etc.).
*   `api/`: Contains all the application logic (models, views, serializers).
*   `db.sqlite3`: The local database file (if copied).
