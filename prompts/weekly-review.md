---
name: weekly-review-pult
description: По воскресеньям в 20:00 пишет суперкраткие итоги недели на «Пульт дня».
---

Подведи суперкраткие итоги недели для дашборда «Пульт дня» (<ARTIFACT_URL>). Загрузи ToolSearch "select:ArtifactData". Часовой пояс <TIMEZONE>. Пользователя зовут <NAME>, пиши по-русски на «ты».

1. Неделя = последние 7 дней по сегодня включительно (пн–вс). Определи даты START и END (YYYY-MM-DD) и ISO-номер недели.
2. ArtifactData query tasks где date >= START и date <= END (игнорируй deleted:true). Посчитай: сделано / всего, сколько задач с movedCount >= 3 ещё открыто (назови до 2 штук), лучший день (больше всего сделанных).
3. ArtifactData query days где date >= START и date <= END: сколько дней закрыто кнопкой (source "button") против автоматически.
4. GitHub, только чтение: `gh api "users/<GITHUB_USER>/events?per_page=100"` за эти 7 дней — сколько пушей и в какие репозитории.
5. text — СУПЕРКРАТКО, максимум 3 строки, без воды и эмодзи. Пример формы:
«Сделано 18 из 24 (75%), лучший день — среда.
Застряли: „Сделать бэкап“ (↷4).
GitHub: 12 пушей, в основном TG_foodBot.»
6. ArtifactData set: collection "reviews", doc_id "week-YYYY-Www" (например week-2026-W43), data {type:"week", period: "напр. 19–25 окт", text, stats:{done, total, closedByButton, stale}, createdAt: сейчас в мс}. Если документ уже есть — прочитай и передай его version как if_version.
Больше ничего не меняй. Ответь одной строкой.