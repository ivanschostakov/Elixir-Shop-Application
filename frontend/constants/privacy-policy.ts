import type { Language } from "@/i18n/translations"

// This document describes the app's data flows, independently of the website offer.
export const PRIVACY_POLICY: Record<Language, string> = {
    ru: `# Конфиденциальность Elixir Peptide
Редакция от 30 сентября 2026 года.

## Какие данные используются
Приложение обрабатывает предоставленные вами данные аккаунта и получателя, адреса, заказы, избранное, переписку и выбранные вложения. При использовании ИИ-дневника сохраняются введённые вами сведения о самочувствии, питании и других записях. Технические сведения об устройстве, сеансах, действиях и уведомлениях используются для работы приложения, аналитики и защиты от злоупотреблений.

## Кому передаются данные
Для исполнения выбранных вами действий необходимые данные получают службы оплаты и доставки, сервисы аккаунта и заказов, сотрудники поддержки и инфраструктура уведомлений. Сообщения общего чата и имя автора видны участникам; сообщения могут синхронизироваться с Telegram. Не публикуйте там личные документы.
После отдельного согласия OpenAI получает отправленные в ИИ сообщения, выбранные файлы и изображения, голос для расшифровки, историю диалога и нужный контекст сохранённого ИИ-дневника. При использовании функций магазина ответ может учитывать сведения о ваших товарах, корзине и заказах. Обработка у внешнего поставщика может происходить за пределами вашей страны.

## Выбор и хранение
ИИ можно не использовать: отказ не закрывает остальные разделы приложения. Согласие на OpenAI можно отозвать на этом экране. Это останавливает новые запросы; уже начатый запрос нельзя отозвать. Переписка и вложения хранятся до удаления соответствующих данных или аккаунта. У OpenAI действуют собственные сроки хранения диалогов, файлов и журналов безопасности:
https://developers.openai.com/api/docs/guides/your-data
Личные вложения ИИ доступны через авторизованный доступ владельца и уполномоченных сотрудников, а не по публичной ссылке.

## Удаление и связь
Удалить аккаунт можно в профиле, в разделе личных данных. Связанные личные данные удаляются, а удаление ресурсов у ИИ-поставщика выполняется в очереди и может занять время. Сведения оформленных заказов могут сохраняться для исполнения заказа и учёта. Копии в Telegram и отдельный аккаунт сайта управляются отдельно. Для исправления данных и вопросов об обработке обратитесь в поддержку приложения или по адресу:
elixirpeptide@yandex.ru`,
    en: `# Elixir Peptide privacy
Updated September 30, 2026.

## Data we use
The app processes the account and recipient details, addresses, orders, favorites, messages and attachments you provide. If you use the AI journal, it stores the wellbeing, nutrition and other entries you choose to enter. Device, session, activity and notification data support app operation, analytics and abuse prevention.

## Data recipients
Information needed for your chosen actions is shared with payment and delivery services, account and order services, support staff and notification infrastructure. Community messages and author names are visible to participants and may sync with Telegram. Do not publish private documents there.
After your separate permission, OpenAI receives messages you send to AI, selected files and images, voice for transcription, conversation history and relevant saved AI journal context. Store features may also use information about your products, basket and orders. External processing may take place outside your country.

## Choice and retention
Using AI is optional; declining does not block the rest of the app. You can withdraw OpenAI permission on this screen. This stops new requests; an already started request cannot be recalled. Messages and attachments remain until the corresponding data or account is deleted. OpenAI has its own retention periods for conversations, files and safety logs:
https://developers.openai.com/api/docs/guides/your-data
Personal AI attachments require authenticated access by the owner or authorized staff; they are not available through public links.

## Deletion and contact
Delete your account from Personal details in your profile. Linked personal data is deleted; removal of AI provider resources is queued and may take time. Submitted order records may remain for fulfillment and accounting. Telegram copies and a separate website account are managed separately. For corrections or privacy questions, use in-app support or email:
elixirpeptide@yandex.ru`,
    kz: `# Elixir Peptide құпиялылығы
2026 жылғы 30 қыркүйектегі нұсқа.

## Қолданылатын деректер
Қолданба сіз берген аккаунт пен алушы деректерін, мекенжайларды, тапсырыстарды, таңдаулыларды, хабарламалар мен тіркемелерді өңдейді. ИИ күнделігін пайдалансаңыз, өзіңіз енгізген хал-жағдай, тамақтану және басқа жазбалар сақталады. Құрылғы, сеанс, әрекет және хабарландыру деректері қолданбаның жұмысына, аналитикаға және теріс пайдаланудан қорғауға қажет.

## Деректер кімге беріледі
Таңдаған әрекеттеріңіз үшін қажетті деректер төлем, жеткізу, аккаунт пен тапсырыс сервистеріне, қолдау қызметіне және хабарландыру инфрақұрылымына беріледі. Ортақ чаттағы хабарламалар мен автор есімі қатысушыларға көрінеді және Telegram-мен синхрондалуы мүмкін. Ол жерде жеке құжаттарды жарияламаңыз.
Бөлек келісімнен кейін OpenAI ИИ-ге жіберілген хабарламаларды, таңдалған файлдар мен суреттерді, мәтінге айналдыру үшін дауысты, диалог тарихын және ИИ күнделігіндегі қажетті контексті алады. Дүкен функциялары тауарлар, себет пен тапсырыстарыңыз туралы мәліметтерді де қолдануы мүмкін. Сыртқы өңдеу еліңізден тыс жерде жүруі мүмкін.

## Таңдау және сақтау
ИИ қолдану міндетті емес: бас тарту басқа бөлімдерді бұғаттамайды. OpenAI-ге келісімді осы экранда қайтарып алуға болады. Бұл жаңа сұрауларды тоқтатады; басталған сұрауды қайтару мүмкін емес. Хабарламалар мен тіркемелер тиісті деректер немесе аккаунт жойылғанға дейін сақталады. OpenAI диалогтар, файлдар мен қауіпсіздік журналдары үшін бөлек сақтау мерзімдерін қолданады:
https://developers.openai.com/api/docs/guides/your-data
Жеке ИИ тіркемелері тек аккаунт иесіне және өкілетті қызметкерлерге авторизация арқылы қолжетімді, ашық сілтемемен берілмейді.

## Жою және байланыс
Аккаунтты профильдегі жеке деректер бөлімінен жоюға болады. Байланысты жеке деректер жойылады; ИИ жеткізушісіндегі ресурстарды жою кезекпен орындалады және уақыт алуы мүмкін. Оформленген тапсырыс деректері орындау мен есепке алу үшін сақталуы мүмкін. Telegram көшірмелері мен сайттың бөлек аккаунты бөлек басқарылады. Деректерді түзету немесе құпиялылық бойынша қолданба қолдауына не мына мекенжайға жазыңыз:
elixirpeptide@yandex.ru`,
}
