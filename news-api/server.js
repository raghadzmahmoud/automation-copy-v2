const express = require("express");
const cors = require("cors");
const { Pool } = require("pg");

const app = express();
app.use(cors());
app.use(express.json());

const pool = new Pool({
  user: "automation_db_mbly_user",
  host: "dpg-d4co200dl3ps73bk1ufg-a.oregon-postgres.render.com",
  database: "automation_db_mbly",
  password: "i33hAvmcwOmFoo54S4Wlv4cslk14ziha",
  port: 5432,
    ssl: {
    rejectUnauthorized: false  // مهم لأن Render يحتاج SSL
  }
});
app.get("/api/test-connection", async (req, res) => {
  try {
    const result = await pool.query("SELECT NOW()");
    res.json({ success: true, serverTime: result.rows[0].now });
  } catch (err) {
    console.error(err);
    res.status(500).json({ success: false, error: err.message });
  }
});

// ------------------------
// Endpoint لجلب الأخبار مع الأقسام
// ------------------------
app.get("/api/news-with-categories", async (req, res) => {
  try {
    const categoriesResult = await pool.query("SELECT id, name FROM categories ORDER BY name");
   const newsResult = await pool.query(`
  SELECT 
    id, 
    title, 
    content_text, 
    content_img, 
    content_video, 
    category_id, 
    published_at,
    tags
  FROM raw_news
  ORDER BY published_at DESC
`);


    res.json({
      categories: categoriesResult.rows,
      news: newsResult.rows,
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Server error" });
  }
});

// ------------------------
// تشغيل السيرفر
// ------------------------
const PORT = 5000;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
