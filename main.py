import nest_asyncio
import re
import glob
import face_recognition
import os

from aiogram import types, executor, Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher import FSMContext

from markups import main_menu, inline_menu, inline_edit_menu
from config import API_TOKEN, HELP, users, bot_password
from functions import load_photo_with_name, parse_filename, show_people
import recognizer
import config


class ProfileStatesGroup(StatesGroup):
    name = State()
    photo = State()

    delete_photo = State()

    uri = State()
    end_rec = State()

    select_person = State()

    edit_idx = State()
    edit_name = State()

    password = State()

    set_ip = State()
    set_port = State()
    set_password = State()


nest_asyncio.apply()

rec = recognizer.Main()
storage = MemoryStorage()
bot = Bot(API_TOKEN)
dp = Dispatcher(bot=bot, storage=storage)

ipv4_pattern = '''^(25[0-5]|2[0-4][0-9]|[0-1]?[0-9][0-9]?)\.(
25[0-5]|2[0-4][0-9]|[0-1]?[0-9][0-9]?)\.(
25[0-5]|2[0-4][0-9]|[0-1]?[0-9][0-9]?)\.(
25[0-5]|2[0-4][0-9]|[0-1]?[0-9][0-9]?)$'''


@dp.message_handler(lambda mes: mes.chat.id not in users, commands=['start'])
async def get_access(message: types.Message):
    await message.answer('Введите пароль для доступа к боту!')
    await ProfileStatesGroup.password.set()
    await message.delete()


@dp.message_handler(state=ProfileStatesGroup.password)
async def check_password(message: types.Message, state: FSMContext):
    if message.text == bot_password:
        users.append(message.chat.id)
        await message.delete()
        await message.answer(f"Boom! 💥 Выберите из меню ниже 👇. Если что-то не понятно, напиши /help",
                             reply_markup=main_menu)
    else:
        await message.answer('В доступе отказано!')
    await state.finish()


@dp.message_handler(lambda mes: mes.chat.id not in users)
async def have_access(message: types.Message):
    await bot.send_message(message.chat.id, 'Создатель не разрешает мне общаться с незнакомыми людьми!')


@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer(f"Boom! 💥 Выберите из меню ниже 👇. Если что-то не понятно, напиши /help",
                         reply_markup=main_menu)
    await message.delete()


@dp.message_handler(commands=['help'])
async def cmd_start(message: types.Message):
    await message.answer(HELP, reply_markup=main_menu, parse_mode='HTML')
    await message.delete()


# --------------------------------------------Добавление фото-----------------------------------------------------------
@dp.message_handler(Text(equals="Добавить фото 📷"), state=[None, '*'])
async def cmd_add(message: types.Message):
    await message.reply("Введи данные человека в формате: Имя Фамилия-Роль (e.g. Иван Иванов-Программист)",
                        reply_markup=inline_menu)
    await ProfileStatesGroup.name.set()


@dp.message_handler(state=ProfileStatesGroup.name)
async def load_name(message: types.Message, state: FSMContext):
    if re.fullmatch(r'[А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+-[А-ЯЁа-яё ]+', message.text):
        async with state.proxy() as data:
            data['name'] = message.text
        await message.answer("Теперь прикрепите фото, на котором хорошо видно лицо человека",
                             reply_markup=inline_menu)
        await ProfileStatesGroup.next()
    else:
        await message.answer(
            "Неверный формат! Введи данные человека в формате: Имя Фамилия-Роль (e.g. Иван Иванов-Программист)",
            reply_markup=inline_menu)


@dp.message_handler(content_types=['photo'], state=ProfileStatesGroup.photo)
async def load_photo(message: types.Message, state: FSMContext):
    await message.photo[-1].download('uploaded/1.jpg')
    image = face_recognition.load_image_file('uploaded/1.jpg')
    enc = face_recognition.face_encodings(image)
    if len(enc) > 1:
        await message.answer(f"⚠️ В кадре больше 1 человека! Выберите другое фото!",
                             reply_markup=inline_menu)
    elif len(enc) == 0:
        await message.answer(f"⚠️ Лицо не было распознано! Выберите другое фото!",
                             reply_markup=inline_menu)
    else:
        async with state.proxy() as data:
            fullname, role = data['name'].split('-')
            path = load_photo_with_name('_'.join(fullname.split()) + '-' + role)
            file = face_recognition.load_image_file(path)
            rec.rec.add_photo(fullname, role, file)
        await message.answer(f"Фото успешно добавлено")
        await state.finish()
# --------------------------------------------Добавление фото-----------------------------------------------------------

# --------------------------------------------Удаление фото-------------------------------------------------------------


@dp.message_handler(Text(equals="Удалить фото ✋🏻"))
async def cmd_del(message: types.Message):
    files = ["png", "jpg"]
    people = glob.glob(f"people/*{files}")
    if len(people) > 0:
        await show_people(message, people, main_menu)
        await message.answer(f"Введите порядковый номер человека (от 1 до {len(people)}), которого хотите удалить",
                             reply_markup=inline_menu)
        await ProfileStatesGroup.delete_photo.set()

        state = Dispatcher.get_current().current_state()
        async with state.proxy() as data:
            data['people'] = people
    else:
        await message.answer("⚠️ Вы не добавляли фото людей!",
                             reply_markup=inline_menu)


@dp.message_handler(state=ProfileStatesGroup.delete_photo)
async def del_photo(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        people = data['people']

    if re.fullmatch('\d+', message.text):
        idx = int(message.text) - 1

        if idx <= -1 or idx >= len(people):
            await message.answer(f"⚠️ Число не попадает в интервал от 1 до {len(people)}",
                                 reply_markup=inline_menu)
        else:
            rec.rec.del_photo(idx)
            #shutil.move(people[idx], "deleted")
            os.remove(people[idx])
            await message.answer(f"Фото №{idx + 1}({people[idx][-4:]}) успешно удалено", reply_markup=main_menu)
            await state.finish()
    else:
        await message.answer(
            f"Неверный формат! Введите порядковый номер человека (от 1 до {len(people)}), которого хотите удалить",
            reply_markup=inline_menu)
# --------------------------------------------Удаление фото------------------------------------------------------------


# --------------------------------------------Вывод всех фото----------------------------------------------------------
@dp.message_handler(Text(equals="Вывести внесенных людей 👀"))
async def cmd_show_all_people(message: types.Message):
    files = ["png", "jpg"]
    people = glob.glob(f"people/*{files}")
    if len(people) > 0:
        await show_people(message, people, main_menu)
    else:
        await message.answer("⚠️ Вы не добавляли фото людей!", reply_markup=main_menu)
# --------------------------------------------Вывод всех фото-----------------------------------------------------------


# --------------------------------------------Вывести человека с фото---------------------------------------------------
@dp.message_handler(Text(equals="Вывести человека с фото 👁️"))
async def cmd_show_person(message: types.Message):
    files = ["png", "jpg"]
    filenames = glob.glob(f"people/*{files}")
    people = []
    for filename in filenames:
        if re.search('[А-ЯЁ][а-яё]+_[А-ЯЁ][а-яё]+-[А-ЯЁа-яё ]+.jpg', filename):
            people.append(filename)
    if len(people) > 0:
        await show_people(message, people, main_menu)
        await message.answer(
            f"Введите порядковый номер человека (от 1 до {len(people)}), фото которого хотите посмотреть",
            reply_markup=inline_menu)
        await ProfileStatesGroup.select_person.set()

        state = Dispatcher.get_current().current_state()
        async with state.proxy() as data:
            data['people'] = people
    else:
        await message.answer("⚠️ Вы не добавляли фото людей!", reply_markup=main_menu)


@dp.message_handler(state=ProfileStatesGroup.select_person)
async def show_person(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        unique_people = data['people']

    if re.fullmatch('\d+', message.text):
        idx = int(message.text) - 1

        if idx <= -1 or idx >= len(unique_people):
            await message.answer(f"⚠️ Число не попадает в интервал от 1 до {len(unique_people)}",
                                 reply_markup=inline_menu)
        else:
            files = ["png", "jpg"]
            people = sorted(glob.glob(f"people/*{files}"), reverse=True)

            current_person = unique_people[idx][:-4]
            for person in people:
                if current_person in person:
                    with open(person, "rb") as photo:
                        full_name, role = parse_filename(person)
                        await message.answer_photo(photo, caption=f"{full_name} -- {role}")
            await state.finish()
    else:
        await message.answer(
            f"Неверный формат! Введите порядковый номер человека (от 1 до {len(unique_people)}), фото которого хотите посмотреть",
            reply_markup=inline_menu)


# --------------------------------------------Вывести человека с фото---------------------------------------------------

# --------------------------------------------Редактировать имя---------------------------------------------------------
@dp.message_handler(Text(equals="Редактировать инф-ию о человеке 📝"))
async def cmd_edit(message: types.Message):
    files = ["png", "jpg"]
    people = glob.glob(f"people/*{files}")
    if len(people) > 0:
        await show_people(message, people, main_menu)
        await message.answer(
            f"Введите порядковый номер человека (от 1 до {len(people)}), которого хотите отредактировать",
            reply_markup=inline_menu)
        await ProfileStatesGroup.edit_idx.set()

        state = Dispatcher.get_current().current_state()
        async with state.proxy() as data:
            data['people'] = people
    else:
        await message.answer("⚠️ Вы не добавляли фото людей!",
                             reply_markup=inline_menu)


@dp.message_handler(state=ProfileStatesGroup.edit_idx)
async def select_person(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        people = data['people']

    if re.fullmatch('\d+', message.text):
        idx = int(message.text) - 1

        if idx <= -1 or idx >= len(people):
            await message.answer(f"⚠️ Число не попадает в интервал от 1 до {len(people)}",
                                 reply_markup=inline_menu)
        else:
            async with state.proxy() as data:
                data['edit_name'] = people[idx]
            await message.answer("Выберете, что вы хотите изменить",
                                 reply_markup=inline_edit_menu)
    else:
        await message.answer(
            f"Неверный формат! Введите порядковый номер человека (от 1 до {len(people)}), фото которого хотите посмотреть",
            reply_markup=inline_menu)


@dp.message_handler(state=ProfileStatesGroup.edit_name)
async def edit_person_name(message: types.Message, state: FSMContext):
    if re.fullmatch(r'[А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+-[А-ЯЁа-яё ]+', message.text):
        async with state.proxy() as data:
            edit_name = data['edit_name']
            os.rename(edit_name, 'people/' + '_'.join(message.text.split()) + '.jpg')

        await message.answer("Имя изменено!")
        await state.finish()
    else:
        await message.answer(
            "Неверный формат! Введи данные человека в формате: Имя_Фамилия-Роль (e.g. Иван_Иванов-Программист)",
            reply_markup=inline_menu)


# --------------------------------------------Редактировать имя---------------------------------------------------------

# --------------------------------------------Закончить распознавание---------------------------------------------------
@dp.message_handler(Text(equals="Закончить распознавание 🚫"), state='*')
async def cmd_end_rec(message: types.Message, state: FSMContext):
    try:
        rec.rec.set_star_title()
        await rec.end()
        await message.reply("Распознавание закончилось")
    except Exception as e:
        await message.answer("❗ Что-то пошло не так! " + str(e))
    finally:
        await state.finish()


# --------------------------------------------Закончить распознавание---------------------------------------------------
# --------------------------------------------OBS config---------------------------------------------------
@dp.message_handler(Text(equals="Настроить OBS ⚙️"))
async def cmd_obs_config(message: types.Message):
    await message.answer("Введите ip OBS сервера! (Пример: 192.168.12.197)", reply_markup=inline_menu)
    await ProfileStatesGroup.set_ip.set()


@dp.message_handler(state=ProfileStatesGroup.set_ip)
async def set_ip_obs(message: types.Message, state: FSMContext):
    if re.fullmatch(ipv4_pattern, message.text):
        config.host = message.text
        await message.answer("Введите порт OBS сервера от 1 до 65535! (Пример: 4445)", reply_markup=inline_menu)
        await ProfileStatesGroup.next()
    else:
        await message.answer("⚠️ Неправильный формат ip! Введите ip OBS сервера! (Пример: 192.168.12.197)",
                             reply_markup=inline_menu)


@dp.message_handler(state=ProfileStatesGroup.set_port)
async def set_port_obs(message: types.Message, state: FSMContext):
    if re.fullmatch("[0-9]+", message.text) and 1 <= int(message.text) <= 65535:
        config.port = int(message.text)
        await message.answer("Введите пароль к OBS серверу!", reply_markup=inline_menu)
        await ProfileStatesGroup.next()
    else:
        await message.answer("⚠️ Неправильный формат порта! Введите порт OBS сервера от 1 до 65535! (Пример: 4445)",
                             reply_markup=inline_menu)


@dp.message_handler(state=ProfileStatesGroup.set_password)
async def set_password_obs(message: types.Message, state: FSMContext):
        config.password = message.text
        await message.answer("OBS подключение настроено!",
                             reply_markup=main_menu)
        await state.finish()
# --------------------------------------------OBS config----------------------------------------------------------------


# --------------------------------------------Начать распознавание------------------------------------------------------
@dp.message_handler(Text(equals="Начать распознавание 🔍"))
async def cmd_start_rec(message: types.Message):
    try:
        rec.rec.connect_obs()
        rec.rec.set_star_title()
        await message.answer("Введите uri вашей камеры (Пример: rtsp://192.168.1.11:554/live)",
                             reply_markup=inline_menu)
        await ProfileStatesGroup.uri.set()
    except Exception as e:
        await message.answer("❗ Ошибка!  " + str(e))


@dp.message_handler(state=ProfileStatesGroup.uri)
async def start_rec(message: types.Message, state: FSMContext):
    await ProfileStatesGroup.next()
    await message.answer("Распознавание началось", reply_markup=main_menu)
    if message.text == '0':
        await rec.start(0)
    else:
        await rec.start(message.text)


# --------------------------------------------Начать распознавание-----------------------------------------------------

@dp.callback_query_handler(state='*')
async def callback_cancel(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == 'cancel':
        await state.finish()
        await callback.answer("Действие отменено!")
    elif callback.data == 'name':
        await callback.answer(
            "А теперь введи данные человека в формате: Имя Фамилия-Роль (e.g. Иван Иванов-Программист)")
        await ProfileStatesGroup.edit_name.set()


@dp.message_handler(state='*')
async def cmd_start(message: types.Message):
    await message.answer("Я не знаю такую команду! Не пиши сам команды, кнопки для кого сделаны?😡",
                         reply_markup=main_menu)


if __name__ == '__main__':
    executor.start_polling(dp,
                           skip_updates=True)
