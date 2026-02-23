# Working Demo – OLAP BI Platform

## Live Demo

To run the working demo locally:

### Prerequisites

- Python 3.9+
- Node.js 18+
- (Optional) OpenAI API key for LLM-based parsing

### Steps

1. **Clone the repository**

   ```bash
   git clone https://github.com/22biba/olap-special-course.git
   cd olap-special-course
   ```

2. **Install backend dependencies**

   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Generate and load data** (from project root)

   ```bash
   python -m data.generate_dataset
   python -m data.load_star_schema
   ```

4. **Start the backend**

   ```bash
   cd backend
   uvicorn main:app --reload --port 8000
   ```

5. **Start the frontend** (in a new terminal)

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

6. **Open the app**

   - **Frontend:** http://localhost:5173  
   - **API docs (Swagger):** http://localhost:8000/docs  
   - **ReDoc:** http://localhost:8000/redoc  

### Sample Questions to Try

| Question | Expected result |
|----------|-----------------|
| Compare Q3 vs Q4 2024 by region | YoY growth by region, best performer |
| What is the total revenue across all years? | Single total |
| How many transactions per category? | Transaction count by category |
| Filter to Electronics in Europe | Revenue for Electronics in Europe |
| Drill Q4 2024 down to months | Oct, Nov, Dec revenue |
| Which category has the highest profit margin? | Top 1 category |
| Identify the worst-performing subcategory | Bottom 1 subcategory |
| What percentage of revenue comes from each region? | Revenue share % by region |

### Offline API Documentation

To view Swagger docs without running the server:

```bash
cd backend
python export_openapi.py
```

Then open `docs/openapi.json` in [Swagger Editor](https://editor.swagger.io) or run:

```bash
npx @redocly/cli preview docs/openapi.json
```

### Optional: Cloud Deployment

For a publicly accessible demo, deploy to:

- **Backend:** [Render](https://render.com), [Railway](https://railway.app), or similar (Python/FastAPI)
- **Frontend:** [Vercel](https://vercel.com) or [Netlify](https://netlify.com) (static/Vite)
- **Database:** Use a persistent DuckDB file or migrate to PostgreSQL for production

See `docker-compose.yml` for containerized setup.
