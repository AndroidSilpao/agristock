# AgriStock

AgriStock is a Django-based livestock and farm record management application. It helps farm users keep animal details, livestock health and feed records, and farm finance in one place.

## Features

- Create an account and sign in to a personal farm workspace.
- View a dashboard with herd counts, monthly income and expenses, feed and health record totals, upcoming health reminders, and recent activity.
- Manage animal profiles with a unique farm tag, name, species, breed, sex, date of birth, status, purchase value, and notes.
- Search and filter animals, and export animal data as CSV.
- Record livestock finance, feed, and health activity, optionally linked to an animal or to the whole farm.
- Track record dates, quantities, units, amounts, notes, and upcoming health due dates.
- Edit, remove, and export farm records as CSV.
- Keep each user's animal and farm records scoped to their own account.

## Built with

- Python and Django
- MySQL (`mysqlclient`)
- HTML templates and static front-end assets

## Requirements

- Python compatible with Django 5.0.14
- MySQL Server

## Getting started

1. Clone the repository and open its directory:

   ```bash
   git clone https://github.com/AndroidSilpao/agristock.git
   cd agristock
   ```

2. Create and activate a virtual environment, then install dependencies:

   ```bash
   python -m venv .venv
   ```

   Windows PowerShell:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   macOS/Linux:

   ```bash
   source .venv/bin/activate
   ```

   Then install the Python packages:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Create a MySQL database named `bsitcrud`. Configure the database connection in `mysite/settings.py` to match your local MySQL username, password, host, and port. The default settings expect `bsitcrud` on `localhost:3306` with the `root` user and an empty password.

4. Set a private Django secret key in your environment. Do not commit a real secret key to Git.

   Windows PowerShell (for the current terminal session):

   ```powershell
   $env:DJANGO_SECRET_KEY = "your-unique-secret-key"
   ```

   macOS/Linux (for the current terminal session):

   ```bash
   export DJANGO_SECRET_KEY="your-unique-secret-key"
   ```

5. Apply migrations and start the development server:

   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

6. Open <http://127.0.0.1:8000/> in your browser and register an account.

## Tests

Run the test suite with:

```bash
pytest
```

## Contributors

- Andrei Silpao
- Nathaniel Torrez
- Mark Anthony Puno
