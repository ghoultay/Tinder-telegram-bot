# Telegram Profile Management Bot

## Overview

This project implements a Telegram bot designed to assist users in creating and managing their profiles. It allows users to upload photos, update their profile information, and find potential partners based on their preferences. The bot integrates with a backend service and MongoDB for data management.

## Features

- **User Management**: Create, update, and retrieve user profiles.
- **Profile Updates**: Modify specific fields in the user profile.
- **Photo Management**: Upload and manage profile photos.
- **Profile Viewing**: Display current profile information and photos.
- **Matching System**: Find potential partners based on user profile and preferences.
- **Interaction Management**: Handle user interactions and responses.

## Architecture

- **Telegram Bot**: Facilitates communication with users through Telegram.
- **Backend Service**: Manages user data and interactions with the bot.
- **MongoDB**: Stores user profiles and photos.
- **GridFS**: Handles large file storage (e.g., photos) in MongoDB.

## Setup

### Prerequisites

- Python 3.x
- MongoDB instance
- Backend service URL (specified in the configuration file)

### Installation

1. **Clone the Repository**:
    ```bash
    git clone https://github.com/ghoultay/telegram-bot-finding-match.git
    cd telegram-bot-finding-match
    ```

2. **Create and Activate a Virtual Environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. **Install Required Packages**:
    ```bash
    pip install python-telegram-bot pymongo requests gridfs
    ```

4. **Configure the Bot**:

    You need two configuration files:

    - **`config_bot_tinder.ini`**: Configuration for MySQL database.
      ```ini
      [mysql]
      host = YOUR_DB_HOST
      database = YOUR_DB_NAME
      user = YOUR_DB_USER
      password = YOUR_DB_PASSWORD
      ```

    - **`bot_config.txt`**: Configuration for the Telegram bot.
      ```ini
      [telegrambot]
      TOKEN = YOUR_TELEGRAM_BOT_TOKEN
      api_id = YOUR_API_ID
      api_hash = YOUR_API_HASH
      bot_name = YOUR_BOT_NAME
      admin_name = YOUR_ADMIN_USERNAME
      service_url = YOUR_SERVICE_URL
      mongo_url = YOUR_MONGO_URL
      ```

## Contributing

1. **Fork the Repository**:
    - Click on the "Fork" button at the top-right of this repository page.

2. **Create a Feature Branch**:
    ```bash
    git checkout -b feature/ghoultay
    ```

3. **Commit Your Changes**:
    ```bash
    git commit -am 'Add new feature'
    ```

4. **Push to the Branch**:
    ```bash
    git push origin feature/ghoultay
    ```

5. **Create a Pull Request**:
    - Go to the "Pull Requests" tab in this repository and create a new pull request from your feature branch.
