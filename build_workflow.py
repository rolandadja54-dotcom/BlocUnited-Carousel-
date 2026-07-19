"""Builds the BlocUnited n8n workflow JSON (with Telegram approval gate)."""
import json

def node(id, name, type, ver, pos, params, creds=None):
    n = {"parameters": params, "id": id, "name": name, "type": type,
         "typeVersion": ver, "position": pos}
    if creds:
        n["credentials"] = creds
    return n

DRIVE = "1kqE-p82pOgMttt7hKn6YoRhBxwZHNL0u"
OUT = "/data/out_deck"
APP = "/data/carousel_engine"
CHAT = "7067149354"
TG_CRED = {"telegramApi": {"id": "REPLACE_TELEGRAM_CRED", "name": "Telegram account"}}
CAP_EXPR = "{{ $('Extract Caption').first().json.data }}"
MEDIA_EXPR = "{{ JSON.stringify($json.url.filter(u => u)) }}"

n = []
n.append(node("n_sched", "Schedule Daily", "n8n-nodes-base.scheduleTrigger", 1.2, [0, 300],
    {"rule": {"interval": [{"field": "days", "triggerAtHour": 9}]}}))
n.append(node("n_build", "Build Carousel (Python)", "n8n-nodes-base.executeCommand", 1, [200, 300],
    {"command": "cd %s && python main.py --research --fal --out %s" % (APP, OUT)}))
n.append(node("n_readcap", "Read Caption", "n8n-nodes-base.readWriteFile", 1, [380, 300],
    {"operation": "read", "fileSelector": "=%s/caption.txt" % OUT, "options": {}}))
n.append(node("n_excap", "Extract Caption", "n8n-nodes-base.extractFromFile", 1, [560, 300],
    {"operation": "text", "binaryPropertyName": "data", "options": {}}))
n.append(node("n_prevread", "Read Slides (Preview)", "n8n-nodes-base.readWriteFile", 1, [740, 300],
    {"operation": "read", "fileSelector": "=%s/slide_*.png" % OUT, "options": {}}))
n.append(node("n_preview", "Preview To Telegram", "n8n-nodes-base.telegram", 1.2, [920, 300],
    {"operation": "sendPhoto", "chatId": CHAT, "binaryData": True,
     "binaryPropertyName": "data", "additionalFields": {}}, TG_CRED))
n.append(node("n_collapse", "Collapse To Single Item", "n8n-nodes-base.code", 2, [1100, 300],
    {"jsCode": "return [{ json: { ready: true } }];"}))
n.append(node("n_ask", "Ask For Approval", "n8n-nodes-base.telegram", 1.2, [1280, 300],
    {"operation": "sendAndWait", "chatId": CHAT,
     "message": "=Approve this carousel for posting?\n\n" + CAP_EXPR,
     "approvalOptions": {"values": {"approvalType": "double"}},
     "options": {"appendAttribution": False}}, TG_CRED))
n.append(node("n_approved", "Approved?", "n8n-nodes-base.if", 2.2, [1460, 300],
    {"conditions": {"options": {"caseSensitive": True, "typeValidation": "strict", "version": 2},
     "conditions": [{"id": "c1", "leftValue": "={{ $json.data.approved }}", "rightValue": True,
                     "operator": {"type": "boolean", "operation": "equals"}}],
     "combinator": "and"}, "options": {}}))
# TRUE branch -> publish
n.append(node("n_pubread", "Read Slides (Publish)", "n8n-nodes-base.readWriteFile", 1, [1660, 180],
    {"operation": "read", "fileSelector": "=%s/slide_*.png" % OUT, "options": {}}))
n.append(node("n_drive", "Upload Slide To Drive", "n8n-nodes-base.googleDrive", 3, [1840, 180],
    {"name": "={{ $binary.data.fileName }}",
     "driveId": {"__rl": True, "value": "My Drive", "mode": "list", "cachedResultName": "My Drive",
                 "cachedResultUrl": "https://drive.google.com/drive/my-drive"},
     "folderId": {"__rl": True, "value": DRIVE, "mode": "list", "cachedResultName": "Frame",
                  "cachedResultUrl": "https://drive.google.com/drive/folders/%s" % DRIVE},
     "options": {}},
    creds={"googleDriveOAuth2Api": {"id": "REPLACE_DRIVE_CRED", "name": "Google Drive account"}}))
n.append(node("n_blmedia", "Upload Media To Blotato", "n8n-nodes-base.httpRequest", 4.2, [2020, 180],
    {"method": "POST", "url": "https://backend.blotato.com/v2/media", "sendHeaders": True,
     "headerParameters": {"parameters": [{"name": "blotato-api-key", "value": "={{ $env.BLOTATO_API_KEY }}"}]},
     "sendBody": True,
     "bodyParameters": {"parameters": [{"name": "url",
        "value": "=https://drive.google.com/uc?export=download&id={{ $('Upload Slide To Drive').item.json.id }}"}]},
     "options": {}}))
n.append(node("n_agg", "Aggregate Media URLs", "n8n-nodes-base.aggregate", 1, [2200, 180],
    {"fieldsToAggregate": {"fieldToAggregate": [{"fieldToAggregate": "url"}]}, "options": {}}))

def pbody(acct, platform, target, cta):
    post = {"post": {"accountId": acct,
                     "content": {"text": "<<CAP>>\n\n" + cta, "mediaUrls": "<<MED>>", "platform": platform},
                     "target": target}}
    s = json.dumps(post, indent=2).replace("<<CAP>>", CAP_EXPR).replace('"<<MED>>"', MEDIA_EXPR)
    return "=" + s

def pnode(id, name, pos, acct, platform, target, cta):
    return node(id, name, "n8n-nodes-base.httpRequest", 4.2, pos,
        {"method": "POST", "url": "https://backend.blotato.com/v2/posts", "sendHeaders": True,
         "headerParameters": {"parameters": [{"name": "blotato-api-key", "value": "={{ $env.BLOTATO_API_KEY }}"}]},
         "sendBody": True, "specifyBody": "json", "jsonBody": pbody(acct, platform, target, cta), "options": {}})

CTA = "Join our community for new AI tools and to connect with fellow founders.\n\nhttps://blocunited.com/newsletter"
n.append(pnode("n_ig", "[Instagram] Publish via Blotato", [2400, -20], "9752", "instagram", {"targetType": "instagram"},
    "New AI tools and founder conversations inside our community. Tap the link in our bio to join."))
n.append(pnode("n_fb", "[Facebook] Publish via Blotato", [2400, 140], "6649", "facebook",
    {"targetType": "facebook", "pageId": "105432422174069"}, CTA))
n.append(pnode("n_x", "[X] Publish via Blotato", [2400, 300], "4675", "twitter", {"targetType": "twitter"}, CTA))
n.append(pnode("n_li", "[LinkedIn] Publish via Blotato", [2400, 460],
    "REPLACE_WITH_LINKEDIN_ACCOUNT_ID", "linkedin", {"targetType": "linkedin"}, CTA))
# FALSE branch
n.append(node("n_reject", "Notify Rejected", "n8n-nodes-base.telegram", 1.2, [1660, 460],
    {"operation": "sendMessage", "chatId": CHAT, "text": "Carousel rejected. Nothing was posted.",
     "additionalFields": {"appendAttribution": False}}, TG_CRED))
# sticky notes
n.append(node("n_note1", "Sticky Note", "n8n-nodes-base.stickyNote", 1, [0, -60],
    {"width": 900, "height": 300, "content":
     "## BlocUnited Carousel (Fully Python + Approval)\n"
     "n8n = trigger, Telegram approval, Drive hosting, Blotato publishing. Creative = Python.\n\n"
     "**Host:** `carousel_engine/` at `/data/carousel_engine`, `pip install pillow requests`.\n"
     "**Env:** `OPENAI_API_KEY`, `TAVILY_API_KEY`, `FAL_KEY`, `BLOTATO_API_KEY`.\n"
     "Adjust `/data/...` paths + Telegram chatId to yours."}))
n.append(node("n_note2", "Sticky Note1", "n8n-nodes-base.stickyNote", 1, [2360, -180],
    {"width": 540, "height": 180, "content":
     "## Before first run\n- Share Drive **\"Frame\"** folder *Anyone with link*.\n"
     "- Set **LinkedIn** accountId.\n- Map Google Drive + Telegram creds on import."}))

c = {
 "Schedule Daily": {"main": [[{"node": "Build Carousel (Python)", "type": "main", "index": 0}]]},
 "Build Carousel (Python)": {"main": [[{"node": "Read Caption", "type": "main", "index": 0}]]},
 "Read Caption": {"main": [[{"node": "Extract Caption", "type": "main", "index": 0}]]},
 "Extract Caption": {"main": [[{"node": "Read Slides (Preview)", "type": "main", "index": 0}]]},
 "Read Slides (Preview)": {"main": [[{"node": "Preview To Telegram", "type": "main", "index": 0}]]},
 "Preview To Telegram": {"main": [[{"node": "Collapse To Single Item", "type": "main", "index": 0}]]},
 "Collapse To Single Item": {"main": [[{"node": "Ask For Approval", "type": "main", "index": 0}]]},
 "Ask For Approval": {"main": [[{"node": "Approved?", "type": "main", "index": 0}]]},
 "Approved?": {"main": [
     [{"node": "Read Slides (Publish)", "type": "main", "index": 0}],
     [{"node": "Notify Rejected", "type": "main", "index": 0}]]},
 "Read Slides (Publish)": {"main": [[{"node": "Upload Slide To Drive", "type": "main", "index": 0}]]},
 "Upload Slide To Drive": {"main": [[{"node": "Upload Media To Blotato", "type": "main", "index": 0}]]},
 "Upload Media To Blotato": {"main": [[{"node": "Aggregate Media URLs", "type": "main", "index": 0}]]},
 "Aggregate Media URLs": {"main": [[
     {"node": "[Instagram] Publish via Blotato", "type": "main", "index": 0},
     {"node": "[Facebook] Publish via Blotato", "type": "main", "index": 0},
     {"node": "[X] Publish via Blotato", "type": "main", "index": 0},
     {"node": "[LinkedIn] Publish via Blotato", "type": "main", "index": 0}]]},
}
wf = {"name": "BlocUnited Carousel (Python)", "nodes": n, "connections": c, "active": False,
      "settings": {"executionOrder": "v1"}, "pinData": {}}
out = "BlocUnited Carousel (Python).json"
json.dump(wf, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
json.load(open(out, encoding="utf-8"))
ig = [x for x in n if x["name"].startswith("[Instagram]")][0]["parameters"]["jsonBody"]
t = ig[1:].replace(CAP_EXPR, "C").replace(MEDIA_EXPR, '["u"]')
json.loads(t)
print("WROTE", out, "| nodes:", len(n), "| bodies valid JSON; approval gate wired")
