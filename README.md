# SiloGenius 🧠

**BYOAI — Bring Your Own AI | Free & Open Source | GPL v3**

SiloGenius is a free, open source content silo generator and article writing pipeline. Generate complete SEO content silos, write full articles, generate AI images and publish directly to WordPress — all from a beautiful web interface.

No subscriptions. No monthly fees. Bring your own API keys.

![SiloGenius Screenshot](docs/screenshot.png)

---

## What It Does

- **Silo Generator** — Enter a keyword, watch a complete content silo stream live into an editable table
- **Article Writer** — Generate outlines and write full articles from your silo
- **Media** — Generate AI images, convert to AVIF and inject into articles automatically
- **Publisher** — Publish articles to WordPress as draft or live with one click
- **Projects** — Track all your silos, see what's written, what's live, what's missing

---

## Supported AI Providers

SiloGenius is BYOAI — Bring Your Own AI. It supports:

| Provider | Used For | Get Key |
|----------|----------|---------|
| OpenRouter | Silo generation, article writing | [openrouter.ai/keys](https://openrouter.ai/keys) |
| Google AI Studio | Image generation (free tier) | [aistudio.google.com](https://aistudio.google.com/apikey) |
| Anthropic | Article writing (optional) | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI | Article writing (optional) | [platform.openai.com](https://platform.openai.com/api-keys) |

> **Free to start:** OpenRouter has free models (Arcee Trinity is recommended). Google AI Studio gives 1,500 free images per day.

---

## Requirements

- Python 3.10 or higher
- pip
- At least one AI provider API key
- A WordPress site with the following configured:
  - REST API enabled (enabled by default on WordPress 4.7+)
  - Permalinks set to anything except Plain (Settings → Permalinks)
  - A WordPress user account with **Editor** role or higher
  - Application Passwords enabled and created for that account
  - **Note:** Application Passwords require HTTPS on live sites. Localhost works without HTTPS.

### WordPress User Permissions

SiloGenius needs at least an **Editor** account to:
- Create and publish posts
- Upload images to the media library
- Create and assign categories and tags

Do NOT use a Subscriber or Contributor account — they do not have enough permissions to publish posts or upload media.

### Enabling Application Passwords

1. Log into WordPress admin as your Editor or Administrator account
2. Go to **Users → Profile**
3. Scroll down to **Application Passwords**
4. If you don't see this section, make sure your site is running HTTPS or is on localhost
5. Enter a name like "SiloGenius" and click **Add New Application Password**
6. Copy the generated password immediately — it will not be shown again
7. Paste it into your `.env` file as `WP_APP_PASSWORD`

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/silogenius.git
cd silogenius
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

> On Windows: `venv\Scripts\activate`

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your environment

```bash
cp env.example .env
nano .env
```

Fill in your API keys and WordPress credentials. At minimum you need:
- `OPENROUTER_API_KEY` — for silo and article generation
- `GOOGLE_API_KEY` — for image generation
- `WP_URL`, `WP_USERNAME`, `WP_APP_PASSWORD` — for WordPress publishing

### 5. Set up WordPress Application Password

In your WordPress admin:
1. Go to **Users → Profile**
2. Scroll to **Application Passwords**
3. Enter a name (e.g. "SiloGenius") and click **Add New**
4. Copy the generated password into your `.env` file as `WP_APP_PASSWORD`

### 6. Run SiloGenius

```bash
python app.py
```

Open your browser and go to:
```
http://localhost:5000
```

---

## Usage

### Step 1 — Generate a Silo

1. Click **Silo Generator** in the sidebar
2. Enter your main keyword (e.g. "Home Coffee Brewing")
3. Select number of passes (1 pass = ~8-12 articles)
4. Click **Generate Silo** and watch the table build live
5. Edit any cells directly in the table
6. Click **Export CSV** to save

> Your CSV is saved to `~/silogenius/silos/`

### Step 2 — Write Articles

1. Click **Article Writer** in the sidebar
2. Click **Load Silo CSV** and select your CSV
3. Check the articles you want to write
4. Click **Generate Outlines** first, then **Write Articles**
5. Or click **Full Pipeline** to do both in one go

> Articles are saved to `~/silogenius/drafts/`

### Step 3 — Generate Images

1. Click **Media** in the sidebar
2. Configure your image settings:
   - Featured and inline image sizes
   - Image style (Cinematic, Cyberpunk, etc.)
   - Additional instructions and brand name
3. Load your CSV and select articles
4. Click **Process Selected**

> Images are uploaded to your WordPress media library automatically

### Step 4 — Publish to WordPress

1. Click **Publisher** in the sidebar
2. Load your CSV
3. Articles show as ✅ Ready, 🌐 Published or ⚠️ No Draft
4. Select articles and choose **Draft** or **Live**
5. Click **Publish Selected**

---

## Project Structure

```
silogenius/
├── app.py                  # Flask web application
├── requirements.txt        # Python dependencies
├── env.example             # Environment template
├── templates/
│   └── index.html          # Main UI
├── static/
│   ├── css/style.css       # Stylesheet
│   └── js/app.js           # Frontend JavaScript
└── ../silogenius/          # Pipeline data folder
    ├── prompts/            # AI prompt templates
    ├── silos/              # Generated CSV files
    ├── outlines/           # Generated outlines
    ├── drafts/             # Generated articles
    └── images/             # Generated images
```

---

## Settings

All settings are configured via the **Settings** page in the UI:

- **AI Providers** — Enter your API key, click **Retrieve Models** to load available models, then select which model to use for Silo generation, Article writing and Image generation independently
- **WordPress** — Enter your site URL, username and application password, click **Test Connection** to verify
- Click **Save Settings** to write everything to your `.env` file

---

## Rate Limits

| Provider | Default Limit | Sleep Between Calls |
|----------|--------------|---------------------|
| OpenRouter (free) | ~20 req/min | 7 seconds |
| Google AI Studio (free) | 2 images/min | 32 seconds |

> A full 24-article silo with images takes approximately 60-90 minutes on free tier models.

---

## Troubleshooting

**Generate Silo does nothing**
- Check your `OPENROUTER_API_KEY` is set correctly in `.env`
- Make sure you have an active internet connection
- Check the Flask terminal for error messages

**Images not generating**
- Check your `GOOGLE_API_KEY` is set correctly
- Make sure `IMAGE_MODEL` contains a valid Gemini model name
- Google AI Studio free tier resets daily at midnight PST

**WordPress connection fails**
- Make sure your WordPress REST API is enabled
- Check that your Application Password has no extra spaces
- Try accessing `http://yoursite.com/wp-json/wp/v2/posts` in your browser

**Articles cut off mid-way**
- Free tier models have token limits
- The pipeline automatically continues articles up to 4 times
- Try a paid model via OpenRouter for longer articles

---

## Contributing

SiloGenius is open source and contributions are welcome!

- Fork the repository
- Create a feature branch
- Submit a pull request

Areas where help is especially welcome:
- Additional AI provider integrations
- OpenRouter image model support
- DALL-E image support
- Internal linking feature
- Schema markup injection
- Syndication tools

---

## License

SiloGenius is licensed under the **GNU General Public License v3.0**.

You are free to use, modify and distribute this software. Any modifications must also be released under GPL v3. You may not take this code, modify it and sell it as a closed source product.

See [LICENSE](LICENSE) for full terms.

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features including internal linking, external linking, web research, syndication and more.

---

## Credits

Built with Python, Flask, Tailwind CSS and a lot of coffee ☕

*Disrupting the bulk content publishing industry one free tool at a time* 😄
