from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

btn_main_menu = KeyboardButton("Главная ✈️")

# --- Main Menu ---
btn_add_photo = KeyboardButton("Добавить фото 📷")
btn_del_photo = KeyboardButton("Удалить фото ✋🏻")
btn_edit = KeyboardButton("Редактировать инф-ию о человеке 📝")
btn_show_names = KeyboardButton("Вывести внесенных людей 👀")
btn_show_person = KeyboardButton("Вывести человека с фото 👁️")
btn_start_recognition = KeyboardButton("Начать распознование 🔍")
btn_end_recognition = KeyboardButton("Закончить распознование 🚫")

main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(btn_add_photo, btn_del_photo)
main_menu.add(btn_edit)
main_menu.add(btn_show_names)
main_menu.add(btn_show_person)
main_menu.add(btn_start_recognition)
main_menu.add(btn_end_recognition)

inline_btn_cancel = InlineKeyboardButton(text="Отмена",
                     callback_data='cancel')

inline_menu = InlineKeyboardMarkup()
inline_menu.add(inline_btn_cancel)

inline_btn_name = InlineKeyboardButton(text="Изменить имя",
                     callback_data='name')
inline_btn_photo = InlineKeyboardButton(text="Поменять фото",
                     callback_data='photo')

inline_edit_menu = InlineKeyboardMarkup()
inline_edit_menu.add(inline_btn_name, inline_btn_photo)
inline_edit_menu.add(inline_btn_cancel)