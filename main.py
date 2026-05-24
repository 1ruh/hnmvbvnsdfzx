from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional
import algorithms
import database

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-User-Key, X-Admin-Key, X-Key-Type",
    "Access-Control-Max-Age": "86400",
}

class CORSMiddleware:
    def __init__(self, app):
        self.app = app
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "OPTIONS":
            response = Response(status_code=200, headers=CORS_HEADERS)
            await response(scope, receive, send)
            return
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                for key, value in CORS_HEADERS.items():
                    headers[key.lower().encode()] = value.encode()
                message["headers"] = list(headers.items())
            await send(message)
        await self.app(scope, receive, send_wrapper)

app = FastAPI(title="Vain Backend")
app.add_middleware(CORSMiddleware)

class PredictionRequest(BaseModel):
    history: List[dict]
    count: int
    algorithm: str = "vain"
    prediction_history: Optional[List[dict]] = []

@app.get("/")
async def root():
    html = """
    <!DOCTYPE html>
    <html>
        <head><style>
            body { background:#0a0a0a; color:#fff; font-family:sans-serif; display:flex; justify-content:center; align-items:center; height:100vh; margin:0; }
            h1 { background:linear-gradient(310deg, #FFF 30%, #aaa 50%, #FFF 70%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; font-size:48px; }
            p { color:#ffffff7b; }
        </style></head>
        <body>
            <div style="text-align:center;">
                <h1>Vain API</h1>
                <p>Backend Operational</p>
            </div>
        </body>
    </html>
    """
    return Response(content=html, media_type="text/html")

@app.post("/debug-history")
async def debug_history(req: PredictionRequest):
    samples = []
    for i, game in enumerate(req.history[:3]):
        info = {"index": i, "type": str(type(game)), "keys": [], "sample_vals": []}
        if isinstance(game, dict):
            info["keys"] = list(game.keys())
            for k, v in game.items():
                val_preview = str(v)[:200] if v else "None"
                info["sample_vals"].append({"key": k, "type": type(v).__name__, "preview": val_preview})
        elif isinstance(game, list):
            info["length"] = len(game)
            info["first_few"] = str(game[:3])[:200]
        samples.append(info)
    parsed = algorithms.parse_tower_rows(req.history)
    return {
        "total_games": len(req.history),
        "parsed_rows": len(parsed),
        "parsed_preview": str(parsed[:10])[:500] if parsed else "empty",
        "samples": samples
    }

@app.post("/predict")
async def predict(req: PredictionRequest, x_user_key: str = Header(...)):
    if not database.is_valid_key(x_user_key):
        raise HTTPException(status_code=401, detail="Invalid key")
        
    algo_map = {
        "vain": algorithms.vain_algo,
        "pastgames": algorithms.past_games,
        "tower_vain": algorithms.tower_vain,
        "tower_frequency": algorithms.tower_frequency,
        "tower_transition": algorithms.tower_transition,
        "tower_pattern": algorithms.tower_pattern,
        "tower_column_correlation": algorithms.tower_column_correlation,
        "tower_edge_analysis": algorithms.tower_edge_analysis,
        "tower_pastgames": algorithms.tower_pastgames,
    }
    
    func = algo_map.get(req.algorithm, algorithms.vain_algo)
    
    try:
        result = func(req.history, req.count, req.prediction_history)
        debug = {}
        if req.algorithm.startswith('tower_'):
            rows = algorithms.parse_tower_rows(req.history)
            debug['parsed_rows'] = len(rows)
            debug['history_len'] = len(req.history)
            if req.history:
                debug['first_game_keys'] = list(req.history[0].keys()) if isinstance(req.history[0], dict) else 'not dict'
        return {"safeIndices": result, "algorithm": req.algorithm, "debug": debug}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin")
async def admin_panel():
    html = """
    <!DOCTYPE html>
    <html>
        <head><style>
            body { background:#0a0a0a; color:#fff; font-family:sans-serif; display:flex; justify-content:center; align-items:center; height:100vh; margin:0; }
            .panel { background:#00000080; backdrop-filter:blur(20px); border:1px solid #252525; padding:30px; border-radius:12px; width:300px; text-align:center; }
            input { width:90%; padding:10px; margin:10px 0; background:#00000033; border:1px solid #252525; color:#fff; border-radius:6px; }
            button { width:100%; padding:10px; background:rgba(255,255,255,0.3); border:1px solid #fff; color:#000; border-radius:6px; cursor:pointer; font-weight:bold; }
            button:hover { backdrop-filter:brightness(2); }
            #result { margin-top:15px; color:#4ade80; word-break:break-all; }
        </style></head>
        <body>
            <div class="panel">
                <h2>Admin Panel</h2>
                <input type="password" id="adminKey" placeholder="Admin Key">
                <select id="keyType" style="width:100%;padding:10px;margin:10px 0;background:#00000033;border:1px solid #252525;color:#fff;border-radius:6px;">
                    <option value="weekly">Weekly (7 days)</option>
                    <option value="monthly">Monthly (30 days)</option>
                    <option value="lifetime">Lifetime</option>
                </select>
                <button onclick="generate()">Generate Key</button>
                <div id="result"></div>
            </div>
            <script>
                async function generate() {
                    const key = document.getElementById('adminKey').value;
                    const type = document.getElementById('keyType').value;
                    const res = await fetch('/admin/generate', {
                        method: 'POST',
                        headers: { 'X-Admin-Key': key, 'X-Key-Type': type }
                    });
                    const data = await res.json();
                    document.getElementById('result').textContent = data.key || data.detail;
                }
            </script>
        </body>
    </html>
    """
    return Response(content=html, media_type="text/html")

@app.post("/admin/generate")
async def generate_key(x_admin_key: str = Header(...), x_key_type: str = Header("weekly")):
    if not database.check_admin(x_admin_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")
    return {"key": database.generate_key(x_key_type)}
