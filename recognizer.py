from __future__ import annotations
import cv2
import numpy as np
import face_recognition
from typing import List, Union
from pathlib import Path

from amcp_pylib.core import Client
from amcp_pylib.module.template import CG_ADD
from obswebsocket import obsws, requests

from typing import Tuple
import asyncio

import threading
import keyboard
import time

from config import port, host, password



class BoundingBox:
    x_left: int
    y_top: int
    x_right: int
    y_bottom: int
    width: int
    height: int

    def __init__(
        self, top_left_corner: Union[List[int], Tuple[int]], width: int, height: int
    ) -> None:
        """
        Constructor to create a BoundingBox using x,y coordinates of top left corner, width and height

        :param top_left_corner: tuple with two coordinates of top left corner of bounding box
        :param width: width of bounding box
        :param height: height of bounding box
        """

        self.x_left, self.y_top = map(int, top_left_corner)
        self.width = int(width)
        self.height = int(height)
        self.x_right = self.x_left + self.width
        self.y_bottom = self.y_top + self.height

    def tlwh(self) -> List[int]:
        """
        Method returns bounding box in the top-left, width, height format

        :return: x,y coordinates of top left corner; width of BB; height of BB
        """
        return self.x_left, self.y_top, self.width, self.height

    def tlbr(self) -> List[int]:
        """
        Method returns bounding box in the top-left, bottom-right format

        :return: x,y coordinates of top left corner; x,y coordinates of bottom right corner
        """
        return self.x_left, self.y_top, self.x_right, self.y_bottom


class Person:
    max_unseen_frames = 20
    id_availability = dict()
    for possible_id in range(1, 11):
        id_availability[possible_id] = True

    id: int
    full_name: str
    role: str
    body_bounding_box: BoundingBox
    face_bounding_box: BoundingBox
    eye_line: int
    body_frame: np.ndarray
    confidence: float
    sorter_id: int

    def __init__(self, frame: np.ndarray, body_bounding_box: BoundingBox, confidence: float) -> None:
        """
        Constructor that creates a person only from body bounding box, other data shoud be assigned later

        :param body_bounding_box: BoundingBox object, representing body of a person
        """
        self.body_bounding_box = body_bounding_box
        self.body_frame = frame[body_bounding_box.y_top:body_bounding_box.y_bottom,
                                body_bounding_box.x_left:body_bounding_box.x_right]
        self.id = None
        self.sorter_id = None
        self.full_name = None
        self.role = None
        self.face_bounding_box = None
        self.eye_line = None
        self.confidence = confidence
        self.last_seen = 0
        self.face_photo = None

    def get_relative_faceBB(self) -> BoundingBox:
        """
        Method calculates coordinates of face BB relative to body BB

        :return: BoundingBox object representing relative face bounding box
        """
        x_face, y_face, width, height = self.face_bounding_box.tlwh()
        x_body, y_body, _, _ = self.body_bounding_box.tlwh()

        return BoundingBox((x_face - x_body, y_face - y_body), width, height)

    def set_id(self, new_id: int) -> None:
        """
        Method that updates id and sorter_id

        :param new_id: an integer id to set
        """
        if self.id is None:
            available_id = Person.__get_next_id()
            if available_id is None:
                print('Deleting person')
                del self
                return

            self.id = available_id
        self.sorter_id = new_id

    @staticmethod
    def __get_next_id():
        for current_id in range(1, 11):
            if Person.id_availability[current_id]:
                Person.id_availability[current_id] = False
                return current_id

        return None

    def update_info(self, new_info: Person) -> None:
        """
        Method updates info about person

        :param new_info: an object of a Person class containing new info
        """
        self.body_bounding_box = new_info.body_bounding_box
        self.body_frame = new_info.body_frame
        self.face_bounding_box = new_info.face_bounding_box
        self.eye_line = new_info.eye_line
        self.confidence = new_info.confidence
        if new_info.id is not None and self.id is None:
            self.id = new_info.id
        else:
            self.set_id(new_info.sorter_id)
        self.last_seen = 0

    def get_middle_point(self) -> Tuple[int]:
        x, y, w, h = self.body_bounding_box.tlwh()
        x_middle = x + w // 2
        y_middle = y + h // 2
        return (x_middle, y_middle)

    def __repr__(self) -> str:
        return f'X: {self.body_bounding_box.x_left} Y: {self.body_bounding_box.y_top} W: {self.body_bounding_box.width} H: {self.body_bounding_box.height} | ID: {self.id if self.id is not None else "None"} ({self.sorter_id if self.sorter_id is not None else "None"}) | Conf: {self.confidence} | Name: {self.full_name if self.full_name is not None else "Unknown"}'


class Recognizer:
    face_images: List[np.ndarray]
    face_names: List[Tuple[str, str]]
    face_encodings: List[np.ndarray]
    
    def __init__(self) -> None:
        """
        Constructor reads directory containing known faces, generates encodings and parses names and roles for them
        """

        self.text = ''
        self.face_images = []
        self.face_names = []
        self.recognized_people = set()

        self.__read_images()
        
        self.face_encodings = [face_recognition.face_encodings(x)[0] for x in self.face_images]
        
        self.client = Client()
        self.client.connect()
        
        self.ws = obsws(host, port, password)
        self.ws.connect()

        self.set_star_title()

    def __read_images(self):
        faces_dir = Path("people")
        faces_dir.mkdir(parents=True, exist_ok=True)

        for file in faces_dir.iterdir():
            fullname, role = Recognizer.__parse_filename(file.name)

            if fullname is None or role is None:
                continue

            self.face_names.append((fullname, role))
            self.face_images.append(face_recognition.load_image_file(file))

    @staticmethod
    def __parse_filename(filename):
        img_extensions = ['jpg', 'jpeg', 'png', 'bmp']
        file_name_parts = filename.split('.')
        file_ext = file_name_parts[-1]

        if len(file_name_parts) != 2:
            print(f'File named incorrectly: {filename}')
            return None, None

        if file_ext not in img_extensions:
            print(f'Unsupported file type: {file_ext}')
            return None, None

        person_name_parts = file_name_parts[0].split('-')
        if len(person_name_parts) < 2 or len(person_name_parts) > 3:
            print(f'File named incorrectly: {filename}')
            return None, None

        if len(person_name_parts) == 3:
            person_name_parts = person_name_parts[:2]

        full_name, role = person_name_parts
        full_name = " ".join(full_name.split('_'))
        role = " ".join(role.split('_'))
        return full_name, role
    
    def add_photo(self, full_name, role, file):
        self.face_images.append(file)
        self.face_names.append((full_name, role))
        enc = face_recognition.face_encodings(file)[0]
        self.face_encodings.append(enc)

    def del_photo(self, num):
        self.face_images.pop(num)
        self.face_names.pop(num)
        self.face_encodings.pop(num)

    def set_star_title(self):
        self.ws.call(requests.SetInputSettings(inputName="detected_name",
                                               inputSettings={"text": f"Тут будет человек!"}))
    
    def send_ndi(self):
        with open('text.txt', 'r') as fin:
            self.client.send(CG_ADD(video_channel=1,
                                    cg_layer=1, template="TITLE",
                                    play_on_load=0,
                                    data=fin.readline().strip()))

    def recognize(self, frame) -> None:
        """
        Method updates people with their names and roles using face recognition
        
        :param people: list of Person-class objects each representing a detected person
        """
        # encodings = face_recognition.face_encodings(frame)
        # for enc in encodings:
        #     matches = face_recognition.compare_faces(self.face_encodings, enc)
        #     try:
        #         index = matches.index(True)
        #         if self.face_names[index][0] not in self.recognized_people:
        #             text = f'<templateData><componentData id=\"Text1\"><data id=\"text\" value=\"{self.face_names[index][0]}\"/></componentData><componentData id=\"Text2\"><data id=\"text\" value=\"{self.face_names[index][1]}\"/></componentData></templateData>'
        #             self.recognized_people.add(self.face_names[index][0])
        #             nl = '\n'
        #             self.ws.call(requests.SetInputSettings(inputName="detected_name",
        #                                                    inputSettings={"text":f"{nl.join(self.face_names[index][0].split())}"}))
        #             keyboard.unhook_all()
        #             keyboard.add_hotkey('ctrl + shift + l', self.send_ndi, args=(text,))
        #     except BaseException:
        #         pass
        encodings = face_recognition.face_encodings(frame)
        if encodings:
            enc = encodings[0]
            matches = face_recognition.compare_faces(self.face_encodings, enc)
            try:
                index = matches.index(True)
                self.text = f'<templateData><componentData id=\"Text1\"><data id=\"text\" value=\"{self.face_names[index][0]}\"/></componentData><componentData id=\"Text2\"><data id=\"text\" value=\"{self.face_names[index][1]}\"/></componentData></templateData>'
                with open('text.txt', 'w') as fin:
                    fin.write(self.text)
                nl = '\n'
                self.ws.call(requests.SetInputSettings(inputName="detected_name",
                                                       inputSettings={"text": f"{nl.join(self.face_names[index][0].split())}"}))

                # self.ws.call(requests.SetInputSettings(inputName="detected_image",
                #                                        inputSettings={
                #                                            "unload": True
                #                                        }))
                # print(self.ws.call(requests.GetInputSettings(inputName="detected_image")))
                # keyboard.unhook_all()
                # keyboard.add_hotkey('ctrl + shift + l', self.send_ndi)
            except BaseException:
                pass

            
class BufferlessVideoCapture:

    def __init__(self) -> None:
        """
        Constructor to create a VideoCapture from OpenCV that doesn't use a buffer for frames
        """
        self.stop_event = threading.Event()
        self.stop_event.set()
        self.cap = cv2.VideoCapture()
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    def is_opened(self):
        return self.cap.isOpened()
    
    def setup(self, uri):
        """
        :param uri: RTSP uri
        """
        self.cap.open(uri)
        self.stop_event.clear()
        reader_thread = threading.Thread(target=self.capture, daemon=True)
        reader_thread.start()
    
    def capture(self) -> None:
        """
        Private method that should be used as Thread's target. Method reads frames from capture and discards any buffer.
        """

        while True:
            self.cap.grab()
            if self.stop_event.is_set():
                break
            

    def read(self):
        """
        Method returns the current frame from the capture

        :return: OpenCV frame
        """

        _, frame = self.cap.retrieve()
        return frame

    def release(self) -> None:
        """
        Method releases OpenCV capture, resets the reading Thread and sets stop_event
        """
        self.stop_event.set()
        time.sleep(0.5)
        self.cap.release()

class Main:
    def __init__(self):
        self.rec = Recognizer()
        self.vid = BufferlessVideoCapture()
        
    async def start(self, uri):
        '''
        uri: rtsp поток
        '''
        self.vid.setup(uri)
        while self.vid.is_opened():
            frame = self.vid.read()
            if frame is not None:
                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                #image = cv2.resize(frame, (640, 480))
                self.rec.recognize(image)
            await asyncio.sleep(0.01)
        await self.end()
    
    async def end(self):
        self.vid.release()            

# class Stream():
#     """Class for managing stream from camera"""

#     def __init__(self, live=True):
#         self.live = live
#         self.live_frame = None
#         self.client = cv2.VideoCapture()
#         self.client.set(cv2.CAP_PROP_BUFFERSIZE, 2)
#         self._start_background_thread()
 
#     def setup(self, uri):
#         self._setup_stream(uri)
    
#     def end(self):
#         self._cleanup_stream()

#     def _setup_stream(self, uri):
#         """Set up the video stream"""
#         self.live_frame = None
#         self.client.open(uri)

#     def _cleanup_stream(self):
#         """Clean up the video stream"""
#         self.client.release()
     
#     def is_opened(self):
#         return self.client.isOpened()

#     def _camera_buffer_thread(self):
#         """Action to perform in thread"""
#         while True:
#             ret, live_frame = self.client.read()
#             if ret:
#                 self.live_frame = live_frame

#     def _start_background_thread(self):
#         """Start the background thread for updating images"""
#         self.thread = threading.Thread(name='camera_buffer', target=self._camera_buffer_thread)
#         self.thread.setDaemon(True)
#         self.thread.start()

#     def is_frame_empty(self, frame):
#         """Checks if the frame is empty"""
#         return str(type(frame)) == str(type(None))

#     def read(self):
#         """Returns a frame from the camera"""
#         if self.live:
#             if not self.is_frame_empty(self.live_frame):
#                 return self.live_frame
#             else:
#                 return None
#         else:
#             # Return from the buffer
#             ret, frame = self.client.read()
#             return frame
        
        
# class Main:
#     def __init__(self):
#         self.rec = Recognizer()
#         self.vid = Stream()
        
#     async def start(self, uri):
#         '''
#         uri: rtsp поток
#         '''
#         self.vid.setup(uri)
#         while self.vid.is_opened():
#             frame = self.vid.read()
#             print(type(frame))
#             if frame is not None:
#                 image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#                 frame = cv2.resize(frame, (1280, 720))
#                 self.rec.recognize(image)
#             await asyncio.sleep(0.1)
    
#     async def end(self):
#         self.vid.end()
