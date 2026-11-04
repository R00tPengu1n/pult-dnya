---
name: monthly-review-pult
description: 25 числа каждого месяца в 20:00 пишет итоги месяца на «Пульт дня».
---

Подведи итоги месяца для дашборда «Пульт дня» (<ARTIFACT_URL>). Загрузи ToolSearch "select:ArtifactData,PushNotification". Часовой пояс <TIMEZONE>. Пользователя зовут <NAME>, пиши по-русски на «ты».

1. Период: с 25 числа прошлого месяца (не включая) по 25 число этого месяца включительно. START и END в формате YYYY-MM-DD.
2. ArtifactData query tasks где date >= START и date <= END (игнорируй deleted:true; если результатов больше 100, листай через cursor). Посчитай: сделано / всего, процент, сколько задач переносилось, топ-3 самых переносимых открытых, сколько было повторяющихся (recurringId) и как часто они выполнялись.
3. ArtifactData query days за период: сколько дней закрыто кнопкой против автоматически.
4. ArtifactData query reviews где type == "week" — итоги недель за период, чтобы увидеть тренд.
5. GitHub, только чтение: `gh api "users/<GITHUB_USER>/events?per_page=100"` (листай страницы, пока даты в периоде) — пуши и PR по репозиториям, самый активный репо.
6. text — кратко, 4–6 строк, без воды и эмодзи: цифры месяца, тренд по неделям (лучше/хуже), что застревает, GitHub, и один конкретный совет на следующий месяц.
7. ArtifactData set: collection "reviews", doc_id "month-YYYY-MM", data {type:"month", period: "напр. 26 сен – 25 окт", text, stats:{done, total, closedByButton, stale}, createdAt: сейчас в мс}. Если документ уже есть — прочитай и передай его version как if_version.
8. PushNotification (status "proactive"): «<NAME>, итоги месяца на пульте: сделано X из Y».
Больше ничего не меняй. Ответь одной строкой.