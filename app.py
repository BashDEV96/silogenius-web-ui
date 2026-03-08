import csv as csv_module
import re as re_module
import base64
import os
import json
import time
import requests
import urllib.request
from flask import Flask, render_template, request, Response, stream_with_context, jsonify
from dotenv import load_dotenv, set_key

load_dotenv()

app = Flask(__name__)

ENV_PATH = os.path.join(os.path.dirname(__file__), '.env')
SLEEP_SECONDS = 7

# ============================================================
# Core API Functions
# ============================================================

def call_api(messages, model_env_key="OPENROUTER_MODEL", stream=True):
    """Consolidated API handler with proper exception management."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv(model_env_key) or os.getenv("OPENROUTER_MODEL")
    
    if not api_key or not model:
        print("Error: Missing API Key or Model configuration.")
        return ""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            stream=stream,
            timeout=120
        )
        response.raise_for_status()

        if stream:
            output = ""
            for line in response.iter_lines():
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            data = json.loads(line[6:])
                            chunk = data["choices"][0]["delta"].get("content", "")
                            output += chunk
                        except json.JSONDecodeError:
                            continue
            return output
        else:
            data = response.json()
            return data["choices"][0]["message"]["content"]

    except requests.exceptions.RequestException as e:
        print(f"API Request failed: {e}")
        return ""
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"Failed to parse API response: {e}")
        return ""

# ============================================================
# Helper Functions
# ============================================================

def load_prompt(filename):
    prompt_path = os.path.join(os.path.dirname(__file__), '..', 'silogenius', 'prompts', filename)
    prompt_path = os.path.abspath(prompt_path)
    with open(prompt_path, 'r') as f:
        return f.read()

def clean_output(text):
    lines = text.strip().split('\n')
    cleaned = []
    for line in lines:
        if not line.strip():
            continue
        if all(c in '|- \t' for c in line.strip()):
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)

def parse_psv(text):
    lines = text.strip().split('\n')
    if not lines:
        return [], []
    headers = []
    data_lines = []
    for line in lines:
        if '|' in line and not all(c in '|- \t' for c in line.strip()):
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if not headers:
                headers = parts
            else:
                if len(parts) >= len(headers) // 2:
                    data_lines.append(parts)
    return headers, data_lines

def slugify(title):
    title = title.lower()
    title = re_module.sub(r'[^\w\s-]', '', title)
    title = re_module.sub(r'[\s_-]+', '-', title)
    return title.strip('-')

def load_silo_csv(filepath):
    rows = []
    with open(filepath, 'r') as f:
        reader = csv_module.DictReader(f, delimiter='|')
        for row in reader:
            cleaned = {k.strip(): v.strip() for k, v in row.items() if k}
            rows.append(cleaned)
    return rows

def format_brief(row):
    return '\n'.join(f"{k}: {v}" for k, v in row.items())

def mask_credential(cred):
    """Masks credentials for safe transmission to the frontend."""
    if not cred:
        return ""
    if len(cred) <= 8:
        return "***"
    return f"{cred[:4]}...{cred[-4:]}"

# ============================================================
# Main Routes
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/test", methods=["GET", "POST"])
def test():
    return jsonify({"status": "working"})

# ============================================================
# Silo Generator
# ============================================================

@app.route("/generate-silo", methods=["POST"])
def generate_silo():
    data = request.get_json()
    keyword = data.get("keyword", "").strip()
    passes = int(data.get("passes", 1))

    if not keyword:
        return {"error": "No keyword provided"}, 400

    def stream():
        try:
            prompt_template = load_prompt('silo_prompt.txt')
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        full_prompt = prompt_template.replace("{main_keyword}", keyword)
        messages = [{"role": "user", "content": full_prompt}]

        all_text = ""
        headers_sent = False
        columns = []
        total_rows = 0

        for pass_num in range(1, passes + 1):
            yield f"data: {json.dumps({'type': 'status', 'message': f'Pass {pass_num} of {passes}...'})}\n\n"

            output = call_api(messages, model_env_key="SILO_MODEL", stream=True)
            
            if not output:
                yield f"data: {json.dumps({'type': 'error', 'message': 'API call failed or timed out'})}\n\n"
                return

            cleaned = clean_output(output)
            all_text += "\n" + cleaned
            messages.append({"role": "assistant", "content": output})

            parsed_headers, rows = parse_psv(all_text)

            if parsed_headers and not headers_sent:
                columns = parsed_headers
                yield f"data: {json.dumps({'type': 'headers', 'columns': columns})}\n\n"
                headers_sent = True

            new_rows = rows[total_rows:]
            for row in new_rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    row_dict[col] = row[i] if i < len(row) else ""
                yield f"data: {json.dumps({'type': 'row', 'row': row_dict})}\n\n"
                time.sleep(0.08)

            total_rows = len(rows)

            if pass_num < passes:
                continue_msg = f"Continue the silo for '{keyword}'. Add more unique articles. Same PSV format, no duplicate titles."
                messages.append({"role": "user", "content": continue_msg})
                time.sleep(SLEEP_SECONDS)

        yield f"data: {json.dumps({'type': 'done', 'total': total_rows})}\n\n"

    return Response(
        stream_with_context(stream()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )

# ============================================================
# Outlines & Article Writer
# ============================================================

@app.route("/generate-outlines", methods=["POST"])
def generate_outlines():
    data = request.get_json()
    csv_path = data.get("csv_path", "")
    selected = data.get("selected", [])

    if not csv_path or not os.path.exists(csv_path):
        return jsonify({"error": "CSV file not found"}), 400

    rows = load_silo_csv(csv_path)
    if selected:
        rows = [r for r in rows if r.get("Title", "") in selected]

    outlines_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'silogenius', 'outlines'))
    os.makedirs(outlines_dir, exist_ok=True)

    def stream():
        total = len(rows)
        for i, row in enumerate(rows, 1):
            title = row.get("Title", f"Article {i}")
            slug = slugify(title)

            yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'generating'})}\n\n"

            try:
                prompt_template = load_prompt('outline_prompt.txt')
                brief = format_brief(row)
                full_prompt = prompt_template.replace("{article_brief}", brief)
                messages = [{"role": "user", "content": full_prompt}]

                output = call_api(messages, model_env_key="ARTICLE_MODEL", stream=False)

                if output:
                    filepath = os.path.join(outlines_dir, f"{slug}-outline.md")
                    with open(filepath, 'w') as f:
                        f.write(output)
                    yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'done'})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'failed'})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'failed', 'error': str(e)})}\n\n"

            if i < total:
                time.sleep(SLEEP_SECONDS)

        yield f"data: {json.dumps({'type': 'done', 'total': total})}\n\n"

    return Response(
        stream_with_context(stream()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )

@app.route("/write-articles", methods=["POST"])
def write_articles():
    data = request.get_json()
    csv_path = data.get("csv_path", "")
    selected = data.get("selected", [])

    if not csv_path or not os.path.exists(csv_path):
        return jsonify({"error": "CSV file not found"}), 400

    rows = load_silo_csv(csv_path)
    if selected:
        rows = [r for r in rows if r.get("Title", "") in selected]

    outlines_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'silogenius', 'outlines'))
    drafts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'silogenius', 'drafts'))
    os.makedirs(drafts_dir, exist_ok=True)

    CONTINUE_PROMPT = "Continue writing the article. Pick up exactly where you left off. Same tone, style, and format. No preamble or commentary. Just continue the article."

    def stream():
        total = len(rows)
        for i, row in enumerate(rows, 1):
            title = row.get("Title", f"Article {i}")
            slug = slugify(title)

            yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'writing'})}\n\n"

            try:
                outline_path = os.path.join(outlines_dir, f"{slug}-outline.md")
                if os.path.exists(outline_path):
                    with open(outline_path, 'r') as f:
                        outline = f.read()
                else:
                    yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'generating outline'})}\n\n"
                    prompt_template = load_prompt('outline_prompt.txt')
                    brief = format_brief(row)
                    full_prompt = prompt_template.replace("{article_brief}", brief)
                    
                    outline = call_api([{"role": "user", "content": full_prompt}], model_env_key="ARTICLE_MODEL", stream=False)
                    
                    if outline:
                        with open(os.path.join(outlines_dir, f"{slug}-outline.md"), 'w') as f:
                            f.write(outline)
                    time.sleep(SLEEP_SECONDS)

                prompt_template = load_prompt('article_prompt.txt')
                brief = format_brief(row)
                full_prompt = prompt_template.replace("{article_brief}", brief).replace("{article_outline}", outline)
                messages = [{"role": "user", "content": full_prompt}]

                output = call_api(messages, model_env_key="ARTICLE_MODEL", stream=False)
                
                full_article = output
                messages.append({"role": "assistant", "content": output})

                max_continues = 4
                continues = 0
                while continues < max_continues:
                    if "## Conclusion" in full_article or "## conclusion" in full_article.lower():
                        break
                    continues += 1
                    time.sleep(SLEEP_SECONDS)
                    messages.append({"role": "user", "content": CONTINUE_PROMPT})
                    
                    continuation = call_api(messages, model_env_key="ARTICLE_MODEL", stream=False)
                    
                    if not continuation:
                        break
                    full_article += "\n" + continuation.strip()
                    messages.append({"role": "assistant", "content": continuation})

                word_count = len(full_article.split())
                filepath = os.path.join(drafts_dir, f"{slug}.md")
                with open(filepath, 'w') as f:
                    f.write(full_article)

                yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'done', 'words': word_count})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'failed', 'error': str(e)})}\n\n"

            if i < total:
                time.sleep(SLEEP_SECONDS)

        yield f"data: {json.dumps({'type': 'done', 'total': total})}\n\n"

    return Response(
        stream_with_context(stream()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )

# ============================================================
# Settings Endpoints
# ============================================================

@app.route("/get-settings", methods=["GET"])
def get_settings():
    return jsonify({
        "anthropic_key": mask_credential(os.getenv("ANTHROPIC_API_KEY", "")),
        "openai_key": mask_credential(os.getenv("OPENAI_API_KEY", "")),
        "google_key": mask_credential(os.getenv("GOOGLE_API_KEY", "")),
        "openrouter_key": mask_credential(os.getenv("OPENROUTER_API_KEY", "")),
        "silo_model": os.getenv("SILO_MODEL", os.getenv("OPENROUTER_MODEL", "")),
        "article_model": os.getenv("ARTICLE_MODEL", os.getenv("OPENROUTER_MODEL", "")),
        "image_model": os.getenv("IMAGE_MODEL", os.getenv("GOOGLE_IMAGE_MODEL", "")),
        "wp_url": os.getenv("WP_URL", ""),
        "wp_username": os.getenv("WP_USERNAME", ""),
        "wp_app_password": mask_credential(os.getenv("WP_APP_PASSWORD", "")),
    })

@app.route("/get-models", methods=["POST"])
def get_models():
    data = request.get_json()
    provider = data.get("provider", "")
    api_key = data.get("api_key", "").strip()

    if not api_key:
        return jsonify({"error": "No API key provided"}), 400

    try:
        if provider == "openrouter":
            response = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
            models = response.json().get("data", [])
            model_list = [m["id"] for m in models if m.get("id")]
            return jsonify({"models": sorted(model_list)})

        elif provider == "anthropic":
            response = requests.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01"
                },
                timeout=10
            )
            models = response.json().get("data", [])
            model_list = [m["id"] for m in models if m.get("id")]
            return jsonify({"models": sorted(model_list)})

        elif provider == "openai":
            response = requests.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
            models = response.json().get("data", [])
            model_list = [m["id"] for m in models if m.get("id")]
            return jsonify({"models": sorted(model_list)})

        elif provider == "google":
            response = requests.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
                timeout=10
            )
            models = response.json().get("models", [])
            model_list = [m["name"].replace("models/", "") for m in models if m.get("name")]
            return jsonify({"models": sorted(model_list)})

        else:
            return jsonify({"error": "Unknown provider"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/save-settings", methods=["POST"])
def save_settings():
    data = request.get_json()

    mapping = {
        "anthropic_key": "ANTHROPIC_API_KEY",
        "openai_key": "OPENAI_API_KEY",
        "google_key": "GOOGLE_API_KEY",
        "openrouter_key": "OPENROUTER_API_KEY",
        "silo_model": "SILO_MODEL",
        "article_model": "ARTICLE_MODEL",
        "image_model": "IMAGE_MODEL",
        "wp_url": "WP_URL",
        "wp_username": "WP_USERNAME",
        "wp_app_password": "WP_APP_PASSWORD",
    }

    try:
        for field, env_key in mapping.items():
            if field in data:
                if not data[field].startswith("***") and "..." not in data[field]:
                    set_key(ENV_PATH, env_key, data[field])
                    os.environ[env_key] = data[field]
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/test-wordpress", methods=["POST"])
def test_wordpress():
    data = request.get_json()
    wp_url = data.get("wp_url", "").rstrip("/")
    wp_username = data.get("wp_username", "")
    wp_password = data.get("wp_app_password", "")

    if not all([wp_url, wp_username, wp_password]):
        return jsonify({"error": "Missing WordPress credentials"}), 400

    try:
        credentials = f"{wp_username}:{wp_password}"
        token = base64.b64encode(credentials.encode()).decode()
        response = requests.get(
            f"{wp_url}/wp-json/wp/v2/posts",
            headers={"Authorization": f"Basic {token}"},
            timeout=10
        )
        if response.status_code == 200:
            return jsonify({"success": True, "message": "Connected successfully!"})
        else:
            return jsonify({"error": f"Connection failed: HTTP {response.status_code}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# Publisher Endpoints
# ============================================================

@app.route("/check-publish-status", methods=["POST"])
def check_publish_status():
    data = request.get_json()
    articles = data.get("articles", [])

    wp_url = os.getenv("WP_URL", "").rstrip("/")
    wp_username = os.getenv("WP_USERNAME", "")
    wp_password = os.getenv("WP_APP_PASSWORD", "")

    drafts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'silogenius', 'drafts'))

    wp_available = bool(wp_url and wp_username and wp_password)
    auth_header = {}
    if wp_available:
        credentials = f"{wp_username}:{wp_password}"
        token = base64.b64encode(credentials.encode()).decode()
        auth_header = {"Authorization": f"Basic {token}"}

    results = {}
    for title in articles:
        slug = slugify(title)
        draft_path = os.path.join(drafts_dir, f"{slug}.md")
        has_draft = os.path.exists(draft_path)

        is_published = False
        post_id = None
        post_url = None
        if wp_available and has_draft:
            try:
                response = requests.get(
                    f"{wp_url}/wp-json/wp/v2/posts",
                    headers=auth_header,
                    params={"slug": slug, "per_page": 1},
                    timeout=5
                )
                if response.status_code == 200:
                    posts = response.json()
                    if posts:
                        is_published = True
                        post_id = posts[0]["id"]
                        post_url = posts[0]["link"]
            except:
                pass

        if is_published:
            results[title] = {"status": "published", "post_id": post_id, "post_url": post_url}
        elif has_draft:
            results[title] = {"status": "ready"}
        else:
            results[title] = {"status": "missing"}

    return jsonify(results)

@app.route("/publish-articles", methods=["POST"])
def publish_articles():
    data = request.get_json()
    csv_path = data.get("csv_path", "")
    selected = data.get("selected", [])
    publish_status = data.get("publish_status", "draft")

    if not csv_path or not os.path.exists(csv_path):
        return jsonify({"error": "CSV file not found"}), 400

    rows = load_silo_csv(csv_path)
    if selected:
        rows = [r for r in rows if r.get("Title", "") in selected]

    wp_url = os.getenv("WP_URL", "").rstrip("/")
    wp_username = os.getenv("WP_USERNAME", "")
    wp_password = os.getenv("WP_APP_PASSWORD", "")
    drafts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'silogenius', 'drafts'))

    credentials = f"{wp_username}:{wp_password}"
    token = base64.b64encode(credentials.encode()).decode()
    auth_headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json"
    }

    def get_or_create_category(category_string):
        parts = [p.strip() for p in category_string.split(">")]
        parent_id = 0
        category_id = 0
        for part in parts:
            try:
                response = requests.get(
                    f"{wp_url}/wp-json/wp/v2/categories",
                    headers=auth_headers,
                    params={"search": part, "parent": parent_id},
                    timeout=10
                )
                categories = response.json()
                existing = [c for c in categories if c["name"].lower() == part.lower()]
                if existing:
                    category_id = existing[0]["id"]
                    parent_id = category_id
                else:
                    response = requests.post(
                        f"{wp_url}/wp-json/wp/v2/categories",
                        headers=auth_headers,
                        json={"name": part, "parent": parent_id},
                        timeout=10
                    )
                    if response.status_code == 201:
                        category_id = response.json()["id"]
                        parent_id = category_id
            except:
                pass
        return category_id

    def get_or_create_tags(tags_string):
        tag_ids = []
        tags = [t.strip() for t in tags_string.split(",")]
        for tag in tags:
            try:
                response = requests.get(
                    f"{wp_url}/wp-json/wp/v2/tags",
                    headers=auth_headers,
                    params={"search": tag},
                    timeout=10
                )
                existing_tags = response.json()
                existing = [t for t in existing_tags if t["name"].lower() == tag.lower()]
                if existing:
                    tag_ids.append(existing[0]["id"])
                else:
                    response = requests.post(
                        f"{wp_url}/wp-json/wp/v2/tags",
                        headers=auth_headers,
                        json={"name": tag},
                        timeout=10
                    )
                    if response.status_code == 201:
                        tag_ids.append(response.json()["id"])
            except:
                pass
        return tag_ids

    def stream():
        total = len(rows)
        for i, row in enumerate(rows, 1):
            title = row.get("Title", f"Article {i}")
            slug = slugify(title)

            yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'publishing'})}\n\n"

            try:
                draft_path = os.path.join(drafts_dir, f"{slug}.md")
                if not os.path.exists(draft_path):
                    yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'failed', 'error': 'No draft file found'})}\n\n"
                    continue

                with open(draft_path, 'r') as f:
                    md_content = f.read()

                lines = md_content.split('\n')
                lines = [l for l in lines if not l.startswith('# ')]
                md_content = '\n'.join(lines)

                try:
                    import markdown
                    html_content = markdown.markdown(md_content, extensions=['extra', 'toc'])
                except ImportError:
                    html_content = f"<p>{md_content}</p>"

                category_string = row.get("Category", "")
                tags_string = row.get("Tags", "")

                category_id = None
                if category_string:
                    category_id = get_or_create_category(category_string)

                tag_ids = []
                if tags_string:
                    tag_ids = get_or_create_tags(tags_string)

                featured_media_id = None
                mediaid_file = os.path.join(drafts_dir, f"{slug}-mediaid.txt")
                if os.path.exists(mediaid_file):
                    try:
                        with open(mediaid_file, 'r') as f:
                            featured_media_id = int(f.read().strip())
                    except:
                        pass

                post_data = {
                    "title": title,
                    "content": html_content,
                    "slug": slug,
                    "status": publish_status,
                }
                if category_id:
                    post_data["categories"] = [category_id]
                if tag_ids:
                    post_data["tags"] = tag_ids
                if featured_media_id:
                    post_data["featured_media"] = featured_media_id

                response = requests.post(
                    f"{wp_url}/wp-json/wp/v2/posts",
                    headers=auth_headers,
                    json=post_data,
                    timeout=30
                )

                if response.status_code == 201:
                    post = response.json()
                    yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'done', 'post_id': post['id'], 'post_url': post['link']})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'failed', 'error': f'HTTP {response.status_code}'})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'failed', 'error': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'total': total})}\n\n"

    return Response(
        stream_with_context(stream()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )

# ============================================================
# Media Endpoints
# ============================================================

def generate_image_google(prompt, api_key, model):
    """Generate image using Google AI Studio API with bypassed safety filters"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        
        # Catch HTTP errors without crashing the script
        if response.status_code != 200:
            print(f"Google API Error ({response.status_code}): {response.text}")
            return None
            
        data = response.json()
        
        # Catch prompt-level safety blocks
        if "promptFeedback" in data and data["promptFeedback"].get("blockReason"):
            print(f"Prompt blocked by safety settings: {data['promptFeedback']['blockReason']}")
            return None
            
        candidates = data.get("candidates", [])
        if not candidates:
            print(f"No candidates returned. Full response: {data}")
            return None
            
        for candidate in candidates:
            # Catch generation-level safety blocks
            if candidate.get("finishReason") == "SAFETY":
                print(f"Image generation blocked mid-process by safety filters.")
                return None
                
            for part in candidate.get("content", {}).get("parts", []):
                if "inlineData" in part:
                    return part["inlineData"]["data"]
                    
    except requests.exceptions.RequestException as e:
        print(f"Network or timeout error calling Google API: {e}")
    except Exception as e:
        print(f"Unexpected error in Google image generation: {e}")
        
    return None

def generate_image(prompt):
    """Route image generation to correct provider based on model name"""
    model = os.getenv("IMAGE_MODEL") or os.getenv("GOOGLE_IMAGE_MODEL", "")
    
    if "gemini" in model.lower():
        api_key = os.getenv("GOOGLE_API_KEY", "")
        return generate_image_google(prompt, api_key, model)
    
    print(f"No image provider found for model: {model}")
    return None

def resize_to_avif(image_data_b64, width, height, output_path):
    """Convert base64 image to AVIF at specified dimensions, safely falling back to JPEG."""
    try:
        from PIL import Image
        import io
        raw = base64.b64decode(image_data_b64)
        img = Image.open(io.BytesIO(raw))
        img = img.convert("RGB")
        img = img.resize((width, height), Image.LANCZOS)
        
        # Try AVIF first
        try:
            img.save(output_path, "AVIF", quality=80)
            return True
        except Exception as avif_error:
            # If system lacks pillow-heif for AVIF, fallback to JPEG
            print(f"AVIF save failed ({avif_error}), falling back to JPEG.")
            jpg_path = output_path.replace('.avif', '.jpg')
            img.save(jpg_path, "JPEG", quality=85)
            return jpg_path
            
    except Exception as e:
        print(f"Image opening/processing failed: {e}")
        return False

def build_image_prompt(article_title, section_heading, ar, style, additional, brand):
    """Assemble image prompt from all settings and force the model to draw."""
    
    # Force the conversational model to generate an image instead of text
    prompt = "Generate a high-quality, scenic illustration representing the following topic: "
    topic = f"'{article_title}'"
    
    if section_heading:
        topic += f", specifically focusing on '{section_heading}'."
    
    parts = [prompt, topic]
    
    if style and style.lower() != "none":
        parts.append(f"The art style should be {style}.")
    if brand:
        parts.append(f"Incorporate a stylish {brand} brand aesthetic.")
    if additional:
        parts.append(additional)
        
    parts.append(f"Format the image in a {ar} aspect ratio. DO NOT write any text or explanations. Only generate the image.")
    
    return " ".join(parts)

def upload_to_wordpress(image_path, title, alt_text, caption, description):
    """Upload image to WordPress media library"""
    wp_url = os.getenv("WP_URL", "").rstrip("/")
    wp_username = os.getenv("WP_USERNAME", "")
    wp_password = os.getenv("WP_APP_PASSWORD", "")
    
    credentials = f"{wp_username}:{wp_password}"
    token = base64.b64encode(credentials.encode()).decode()
    
    ext = os.path.splitext(image_path)[1].lower()
    mime_types = {'.avif': 'image/avif', '.jpg': 'image/jpeg', '.png': 'image/png'}
    mime_type = mime_types.get(ext, 'image/jpeg')
    filename = os.path.basename(image_path)
    
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    response = requests.post(
        f"{wp_url}/wp-json/wp/v2/media",
        headers={
            "Authorization": f"Basic {token}",
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": mime_type,
        },
        data=image_data,
        timeout=30
    )
    
    if response.status_code == 201:
        media = response.json()
        media_id = media["id"]
        source_url = media.get("source_url") # Patched: Extract URL from response
        
        requests.post(
            f"{wp_url}/wp-json/wp/v2/media/{media_id}",
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json"
            },
            json={
                "title": title,
                "alt_text": alt_text,
                "caption": caption,
                "description": description
            },
            timeout=10
        )
        return media_id, source_url
    return None, None

def get_h2_sections(markdown_text):
    """Extract H2 section headings from markdown"""
    sections = []
    skip_patterns = ['faq', 'conclusion', 'key takeaway', 'summary', 'final thought']
    for line in markdown_text.split('\n'):
        if line.startswith('## '):
            heading = line[3:].strip()
            if not any(skip in heading.lower() for skip in skip_patterns):
                sections.append(heading)
    return sections

def inject_images_into_markdown(markdown_text, image_data_list, layout):
    """Inject image HTML into markdown at H2 boundaries"""
    lines = markdown_text.split('\n')
    result = []
    h2_count = 0
    image_index = 0

    for line in lines:
        result.append(line)
        if line.startswith('## '):
            heading = line[3:].strip()
            skip_patterns = ['faq', 'conclusion', 'key takeaway', 'summary', 'final thought']
            if any(skip in heading.lower() for skip in skip_patterns):
                continue
            h2_count += 1
            if h2_count == 1:
                continue
            should_inject = False
            if layout == 'every':
                should_inject = True
            elif layout == 'every2' and h2_count % 2 == 0:
                should_inject = True
            elif layout == 'every3' and h2_count % 3 == 0:
                should_inject = True

            if should_inject and image_index < len(image_data_list):
                img = image_data_list[image_index]
                result.append(f'\n![{img["alt"]}]({img["url"]})\n')
                image_index += 1

    return '\n'.join(result)

@app.route("/process-media", methods=["POST"])
def process_media():
    data = request.get_json()
    csv_path = data.get("csv_path", "")
    selected = data.get("selected", [])
    
    featured_size = data.get("featured_size", "1344x768")
    inline_size = data.get("inline_size", "1344x768")
    style = data.get("style", "None")
    additional = data.get("additional", "")
    brand = data.get("brand", "")
    alt_mode = data.get("alt_mode", "keyword")
    layout = data.get("layout", "every2")

    if not csv_path or not os.path.exists(csv_path):
        return jsonify({"error": "CSV file not found"}), 400

    rows = load_silo_csv(csv_path)
    if selected:
        rows = [r for r in rows if r.get("Title", "") in selected]

    drafts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'silogenius', 'drafts'))
    images_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'silogenius', 'images'))
    os.makedirs(images_dir, exist_ok=True)

    def parse_size(size_str):
        parts = size_str.split('x')
        return int(parts[0]), int(parts[1])

    fw, fh = parse_size(featured_size)
    iw, ih = parse_size(inline_size)
    ar_map = {
        '1344x768': '16:9', '1280x704': '20:11', '1152x768': '3:2',
        '1024x768': '4:3', '1024x640': '8:5', '960x768': '5:4',
        '1024x1024': '1:1', '768x1344': '9:16'
    }
    far = ar_map.get(featured_size, '16:9')
    iar = ar_map.get(inline_size, '16:9')

    inline_counts = {
        'x-small': 1, 'small': 2, 'medium': 3, 'large': 4, 'pillar': 4
    }

    RATE_LIMIT_SLEEP = 32

    def stream():
        total = len(rows)
        for i, row in enumerate(rows, 1):
            title = row.get("Title", f"Article {i}")
            slug = slugify(title)
            keyword = row.get("Main Keyword", title)
            article_size = row.get("Article Size", "").lower().split()[0]
            nlp_keywords = row.get("NLP Keywords", "")

            yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'starting'})}\n\n"

            try:
                draft_path = os.path.join(drafts_dir, f"{slug}.md")
                if not os.path.exists(draft_path):
                    yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'failed', 'error': 'No draft found'})}\n\n"
                    continue

                with open(draft_path, 'r') as f:
                    md_content = f.read()

                h2_sections = get_h2_sections(md_content)
                inline_count = inline_counts.get(article_size, 2)
                
                if alt_mode == 'keyword':
                    first_alt = keyword
                    other_alt = keyword
                else:
                    first_alt = keyword
                    other_alt = f"{title} illustration"

                uploaded_images = []

                # --- FEATURED IMAGE GENERATION ---
                yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'featured image'})}\n\n"
                
                featured_prompt = build_image_prompt(title, "", far, style, additional, brand)
                featured_b64 = generate_image(featured_prompt)
                
                if not featured_b64:
                    yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'featured failed: API Generation Error'})}\n\n"
                else:
                    featured_path = os.path.join(images_dir, f"{slug}-featured.avif")
                    result = resize_to_avif(featured_b64, fw, fh, featured_path)
                    
                    if not result:
                        yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'featured failed: Image Processing Error'})}\n\n"
                    else:
                        actual_path = featured_path if result is True else result
                        media_id, _ = upload_to_wordpress(
                            actual_path,
                            title=f"{title} featured image",
                            alt_text=first_alt,
                            caption=title,
                            description=f"Featured image for {title}"
                        )
                        if not media_id:
                            yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'featured failed: WP Upload Error'})}\n\n"
                        else:
                            mediaid_file = os.path.join(drafts_dir, f"{slug}-mediaid.txt")
                            with open(mediaid_file, 'w') as f:
                                f.write(str(media_id))
                            yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'featured done', 'media_id': media_id})}\n\n"

                time.sleep(RATE_LIMIT_SLEEP)

                # --- INLINE IMAGE GENERATION ---
                for img_num in range(inline_count):
                    section = h2_sections[img_num] if img_num < len(h2_sections) else title
                    
                    yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': f'inline image {img_num+1}/{inline_count}'})}\n\n"
                    
                    inline_prompt = build_image_prompt(title, section, iar, style, additional, brand)
                    inline_b64 = generate_image(inline_prompt)
                    
                    if not inline_b64:
                         yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': f'inline {img_num+1} failed: API Generation Error'})}\n\n"
                    else:
                        inline_path = os.path.join(images_dir, f"{slug}-inline-{img_num+1}.avif")
                        result = resize_to_avif(inline_b64, iw, ih, inline_path)
                        
                        if not result:
                            yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': f'inline {img_num+1} failed: Image Processing Error'})}\n\n"
                        else:
                            actual_path = inline_path if result is True else result
                            
                            alt = first_alt if img_num == 0 else other_alt
                            nlp_list = [k.strip() for k in nlp_keywords.split(',')]
                            if img_num > 0 and img_num < len(nlp_list):
                                alt = nlp_list[img_num]
                            
                            media_id, source_url = upload_to_wordpress(
                                actual_path,
                                title=f"{title} - {section}",
                                alt_text=alt,
                                caption=f"{title} — {section}",
                                description=f"Image for {title}, section: {section}"
                            )
                            if not media_id:
                                yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': f'inline {img_num+1} failed: WP Upload Error'})}\n\n"
                            else:
                                uploaded_images.append({
                                    "alt": alt,
                                    "url": source_url
                                })
                    
                    if img_num < inline_count - 1:
                        time.sleep(RATE_LIMIT_SLEEP)

                if uploaded_images:
                    updated_md = inject_images_into_markdown(md_content, uploaded_images, layout)
                    with open(draft_path, 'w') as f:
                        f.write(updated_md)

                yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'done', 'images': len(uploaded_images)})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'type': 'progress', 'current': i, 'total': total, 'title': title, 'status': 'failed', 'error': str(e)})}\n\n"

            if i < total:
                time.sleep(RATE_LIMIT_SLEEP)

        yield f"data: {json.dumps({'type': 'done', 'total': total})}\n\n"

    return Response(
        stream_with_context(stream()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )
# ============================================================
# Projects Endpoints — add these to app.py before app.run()
# ============================================================

@app.route("/get-projects", methods=["GET"])
def get_projects():
    silos_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'silogenius', 'silos'))
    drafts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'silogenius', 'drafts'))
    outlines_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'silogenius', 'outlines'))

    os.makedirs(silos_dir, exist_ok=True)

    projects = []

    try:
        csv_files = [f for f in os.listdir(silos_dir) if f.endswith('.csv')]

        wp_url = os.getenv("WP_URL", "").rstrip("/")
        wp_username = os.getenv("WP_USERNAME", "")
        wp_password = os.getenv("WP_APP_PASSWORD", "")
        wp_available = bool(wp_url and wp_username and wp_password)

        auth_header = {}
        if wp_available:
            credentials = f"{wp_username}:{wp_password}"
            token = base64.b64encode(credentials.encode()).decode()
            auth_header = {"Authorization": f"Basic {token}"}

        for csv_file in sorted(csv_files):
            csv_path = os.path.join(silos_dir, csv_file)
            try:
                rows = load_silo_csv(csv_path)
                total = len(rows)
                keyword = rows[0].get("Main Keyword", csv_file.replace('.csv', '')) if rows else csv_file

                written = 0
                published = 0
                outlined = 0

                for row in rows:
                    title = row.get("Title", "")
                    slug = slugify(title)

                    # Check outline
                    if os.path.exists(os.path.join(outlines_dir, f"{slug}-outline.md")):
                        outlined += 1

                    # Check draft
                    if os.path.exists(os.path.join(drafts_dir, f"{slug}.md")):
                        written += 1

                    # Check WordPress
                    if wp_available and title:
                        try:
                            response = requests.get(
                                f"{wp_url}/wp-json/wp/v2/posts",
                                headers=auth_header,
                                params={"slug": slug, "per_page": 1},
                                timeout=3
                            )
                            if response.status_code == 200 and response.json():
                                published += 1
                        except:
                            pass

                projects.append({
                    "filename": csv_file,
                    "path": csv_path,
                    "keyword": keyword,
                    "total": total,
                    "outlined": outlined,
                    "written": written,
                    "published": published,
                    "missing": total - written
                })

            except Exception as e:
                projects.append({
                    "filename": csv_file,
                    "path": csv_path,
                    "keyword": csv_file,
                    "total": 0,
                    "outlined": 0,
                    "written": 0,
                    "published": 0,
                    "missing": 0,
                    "error": str(e)
                })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"projects": projects})


@app.route("/delete-project", methods=["POST"])
def delete_project():
    data = request.get_json()
    filename = data.get("filename", "")

    silos_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'silogenius', 'silos'))
    csv_path = os.path.join(silos_dir, filename)

    if not os.path.exists(csv_path):
        return jsonify({"error": "File not found"}), 404

    try:
        os.remove(csv_path)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/read-csv", methods=["GET"])
def read_csv():
    path = request.args.get("path", "")
    if not path or not os.path.exists(path):
        return "File not found", 404
    with open(path, 'r') as f:
        return f.read(), 200, {'Content-Type': 'text/plain'}   
# ============================================================
# Application Entry Point
# ============================================================

if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)