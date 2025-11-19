import { useState, useEffect } from "react";
import "./News.css";

function News() {
  const [categories, setCategories] = useState([]);
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [newsList, setNewsList] = useState([]);
  const [popupContent, setPopupContent] = useState(null);
const categoryColors = {
  1: "#4DA1FF", // أزرق بارد
  2: "#6CB8FF", // أزرق سماوي
  3: "#4EC5D4", // فيروز بارد
  4: "#7AD3E0", // سماوي باهت
  5: "#8ED1FF", // أزرق باهت
  6: "#A3E0FF", // ثلجي فاتح
  7: "#66A6E8", // أزرق ضبابي
  8: "#5FC7C0", // تركوازي
  9: "#8FB7FF", // أزرق بنفسجي باهت
  10: "#7FA8D6", // أزرق رمادي
  11: "#A6C8FF" // أزرق ثلجي لطيف
};


  useEffect(() => {
    fetch("http://localhost:5000/api/news-with-categories")
      .then((res) => res.json())
      .then((data) => {
        setCategories(data.categories);
        const sortedNews = data.news.sort(
          (a, b) => new Date(b.published_at) - new Date(a.published_at)
        );
        setNewsList(sortedNews);
      })
      .catch((err) => console.error(err));
  }, []);

  const handleCategoryChange = (id) => {
    setSelectedCategories((prev) =>
      prev.includes(id) ? prev.filter((cid) => cid !== id) : [...prev, id]
    );
  };

  const filteredNews =
    selectedCategories.length === 0
      ? newsList
      : newsList.filter((n) => selectedCategories.includes(n.category_id));

  const openPopup = (news) => setPopupContent(news);
  const closePopup = () => setPopupContent(null);

  return (
    <div className="news-container">
      {/* Sidebar */}
      <aside className="news-sidebar">
        <h2>الأقسام</h2>
        {categories.map((cat) => (
          <div key={cat.id}>
            <label>
              <input
                type="checkbox"
                checked={selectedCategories.includes(cat.id)}
                onChange={() => handleCategoryChange(cat.id)}
              />
              {cat.name}
            </label>
          </div>
        ))}
      </aside>

      {/* Main News Grid */}
      <main className="news-main">
        <h2>آخر الأخبار</h2>
        {filteredNews.length === 0 ? (
          <p>لا توجد أخبار متاحة.</p>
        ) : (
          <div className="news-grid">
            {filteredNews.map((n) => {
              const hasImage = n.content_img?.trim().length > 0;
              const hasVideo = n.content_video?.trim().length > 0;

              const tags = n.tags
                ? n.tags
                    .split(",")
                    .map((t) => t.trim())
                    .filter((t) => t.length > 0)
                : [];

              return (
<div
  key={n.id}
  className="news-card"
  style={{ borderRight: `6px solid ${categoryColors[n.category_id]}` }}
  onClick={() => openPopup(n)}
>
                  {/* الكارد الخارجي: صورة أو فيديو */}
                  {hasImage ? (
                    <img src={n.content_img} alt={n.title} className="news-card-media" />
                  ) : hasVideo ? (
                    <video src={n.content_video} className="news-card-media" controls />
                  ) : null}

                  <div className="news-card-content">
                    <h3>{n.title}</h3>
<div
  className="category-badge"
  style={{ backgroundColor: categoryColors[n.category_id] }}
>
  {categories.find(c => c.id === n.category_id)?.name}
</div>

                    {/* Tags */}
                    {tags.length > 0 && (
                      <div className="news-tags">
                        {tags.map((tag, idx) => (
                      <span
  key={idx}
  className="tag"
  style={{ backgroundColor: categoryColors[n.category_id] }}
>
  #{tag.replace(/_/g, " ")}
</span>

                        ))}
                      </div>
                    )}

                    <p className="news-date">
                      {new Date(n.published_at).toLocaleString("ar")}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* Popup */}
      {popupContent && (
        <div className="news-popup-overlay" onClick={closePopup}>
          <div className="news-popup" onClick={(e) => e.stopPropagation()}>
            <button className="popup-close" onClick={closePopup}>
              ✖
            </button>

            <h2>{popupContent.title}</h2>

            {/* Video */}
            {popupContent.content_video?.trim().length > 0 && (
              <video controls src={popupContent.content_video} className="popup-media" />
            )}

            {/* Text content */}
            {popupContent.content_text && (
              <p className="popup-text">{popupContent.content_text}</p>
            )}

            {/* Tags in popup */}
            {popupContent.tags?.trim() && (
              <div className="news-tags">
                {popupContent.tags
                  .split(",")
                  .map((t) => t.trim())
                  .filter((t) => t.length > 0)
                  .map((tag, idx) => (
                    <span key={idx} className="tag">
                      #{tag.replace(/_/g, " ")}
                    </span>
                  ))}
              </div>
            )}

            <p className="published-date">
              <strong>تاريخ النشر:</strong>{" "}
              {new Date(popupContent.published_at).toLocaleString("ar")}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default News;
