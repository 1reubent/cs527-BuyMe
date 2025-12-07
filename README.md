## Steps to run the project:

### Prerequisites

- **Python 3.11 or higher**
- **pip** (packaged with Python)

### Setup Steps

1. **Clone the repository:**

   ```bash
   git clone <repo-url>
   cd buyme
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**

   ```bash
   python app.py
   ```

5. **Access the application:**
   - Open your browser to `http://localhost:5000` or the URL shown in the terminal
   - The database will be automatically created in the `instance/` folder as `buyme.sqlite3`

### Notes

- Uses SQLite, so no external MySQL setup is needed. `buyme_database.sql` is kept for reference.
- The app initializes the database on first run, including all models.
- `instance/buyme.sqlite3` is not committed, so each collaborator starts with a fresh database.
- uv reference https://docs.astral.sh/uv/reference/cli/
