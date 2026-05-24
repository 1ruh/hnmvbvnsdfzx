# Vain Backend Setup Guide

## 1. Deploy to Render

1. Push the `vain-backend` folder to a GitHub repository
2. Go to https://render.com and create a new **Web Service**
3. Connect your repository
4. Configure:
   - **Name**: vain-api
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

5. Add a **Redis** instance:
   - Go to Dashboard > New > Redis
   - Choose free tier
   - Copy the **Internal Connection URL**

6. Add Environment Variable to your Web Service:
   - Key: `REDIS_URL`
   - Value: `redis://<your-redis-url>`

7. Deploy and wait for build to complete

## 2. Update Userscript

1. Open `Midnight - bloxflip Mines Predictor-2.2.user.js`
2. Find line ~16: `const VAIN_API_URL = "https://your-render-app.onrender.com";`
3. Replace with your actual Render URL (e.g., `https://vain-api.onrender.com`)

## 3. Generate Keys

1. Go to `https://your-render-app.onrender.com/admin`
2. Enter admin key: `9001`
3. Click **Generate Key**
4. Copy the generated key and give it to users

## 4. User Login

Users enter their key in the login screen. The key is validated against Redis before allowing access.

## Security Notes

- All algorithm logic runs server-side (hidden from users)
- Keys are stored in Redis with prefix `vain_key:`
- Admin key is hardcoded as `9001` (change in `database.py` if needed)
- API requires `X-User-Key` header for all prediction requests
