import shutil
import glob


def load_photo_with_name(name: str):
    count = len(glob.glob(f'people/{name}*.jpg'))
    if count > 0 :
        path = f"people/{name}-{count + 1}.jpg"
        shutil.move("uploaded/1.jpg", path)
    else:
        path = f"people/{name}.jpg"
        shutil.move("uploaded/1.jpg", path)
    return path


def parse_filename(filename):
    name = filename[7:-4]
    full_name, role = name[:name.index('-')], name[name.index('-') + 1:]
    full_name = " ".join(full_name.split('_'))
    return full_name, role


async def show_people(message, people, main_menu):
    for idx, person in enumerate(people):
        full_name, role = parse_filename(person)
        await message.answer(f"{idx + 1}) {full_name} -- {role}")
    await message.answer("Текущая база людей", reply_markup=main_menu)