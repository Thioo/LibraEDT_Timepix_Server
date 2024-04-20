"""
Author: Moussa Faye
Date: 2023-05-02

Description:
    This class is responsible for handling the communication between the client and the server.
    The server is responsible for acquiring images from the camera and sending them to the client.
    The client can request a single image or multiple images.
    The server will send the images to the client in the form of a numpy array.
"""

import socket
import struct
import threading
import time

import numpy as np
import tifffile
from win32api import GetAsyncKeyState

# from CCameraInterface import CCameraInterface
from CCameraInterface_Marco import CCameraInterface


class CServer:

    def __init__(self, _tpxInterface: CCameraInterface):
        print("CServer - Constructor")

        # Possible messages:
        self._GRAB_SINGLE_IMG_REQ_ = 1337
        self._GRAB_MULTIPLE_IMG_REQ_ = 1338
        self._GRAB_MULTIPLE_IMG_STOP_REQ_ = 1339
        self._UPDATE_EXPOSURE_TIME_ = 1340

        # constants
        self.IMG_DATA_SIZE = 512 * 512 * 2

        # Create a TCP/IP socket
        self.listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind the socket
        server_address = ('', 12195)  # Port==12195 :)
        self.listen_sock.bind(server_address)

        # Listen for 1 possible client ^^
        self.listen_sock.listen(1)

        self.cameraObject = _tpxInterface
        self.stopServer = False
        self.stopImageAcquisitionLoop = False
        self.stopRecvLoop = False

    def __del__(self):
        print("CServer - Destructor")

        self.listen_sock.close()
        self.client_sock.close()

        pass

    def send_all_data(self, data_to_send):
        total_bytes_sent = 0
        while total_bytes_sent < self.IMG_DATA_SIZE:
            print("Sending {}".format(data_to_send[:10]))
            sent = self.client_sock.send(data_to_send[total_bytes_sent:])
            if not sent:
                print("Error@ send_all_data -> sent == 0")
                break
            total_bytes_sent += sent
            print("Num of bytes sent: {}".format(total_bytes_sent))

    def recv_thread_loop(self):
        print("recv_thread_loop -> Start")

        while True:
            client_request = self.client_sock.recv(12)
            request_id, expTime, frames_limit = struct.unpack('iii', client_request)
            if request_id == self._GRAB_MULTIPLE_IMG_STOP_REQ_:
                print("Interrupting infinite loop")
                self.stopImageAcquisitionLoop = True
                break
            if request_id == self._UPDATE_EXPOSURE_TIME_:
                self.cameraObject.exposure_time = expTime

            if self.stopRecvLoop:
                print("self.stopRecvLoop == True")
                break

        print("recv_thread_loop -> End")

    def on_grab_multiple_limited_img_request(self, _num_frames_limit):
        print("on_grab_multiple_limited_img_request - Buggy, DO NOT USE FOR NOW...")
        frameCount = 0
        self.stopRecvLoop = False
        recv_thread = threading.Thread(target=self.recv_thread_loop)
        recv_thread.start()
        while _num_frames_limit > frameCount:
            start_time = time.time()
            frameCount += 1
            # fileName = "test_data/" + str(frameCount) + ".tiff"
            # img_data = self.cameraObject.grab_image_from_detector_debug(fileName)
            img_data = self.cameraObject.grab_image_from_detector()
            if self.stopImageAcquisitionLoop or _num_frames_limit == frameCount:
                img_data[-1] = 1 # This is so that our c++ client knows which one is the last frame sent
                self.stopRecvLoop = True

            print("Data number: ", frameCount)
            print("Sending {}".format(img_data.reshape(-1)[:10]))
            self.client_sock.sendall(img_data)

            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000
            print(f"Elapsed time: {elapsed_time:.5f} ms")

        recv_thread.join()
        print("recv_thread has joined!")

    def on_grab_multiple_unlimited_img_request(self):
        """

        """
        print("on_grab_multiple_unlimited_img_request")

        # Create the thread responsible for checking whether or not, the client has asked to stop the loop

        frameCount = 0
        realCounter = 0
        self.stopImageAcquisitionLoop = False
        recv_thread = threading.Thread(target=self.recv_thread_loop)
        recv_thread.start()

        while not self.stopImageAcquisitionLoop:
            frameCount += 1
            realCounter += 1
            start_time = time.time()
            fileName = "test_data/" + str(frameCount) + ".tiff"
            print(fileName)
            img_data = self.cameraObject.grab_image_from_detector_debug(fileName)
            print("Data number: ", realCounter)
            print("Sending {}".format(img_data.reshape(-1)[:10]))
            if self.stopImageAcquisitionLoop:
                img_data[-1] = 1  # This is so that our c++ client knows which one is the last frame sent
            self.client_sock.sendall(img_data)
            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000
            print(f"Elapsed time: {elapsed_time:.5f} ms")

            if frameCount >= 40:
                frameCount = 1

        recv_thread.join()
        print("recv_thread has joined!")

    def core(self):
        print("CServer - core")
        while self.stopServer is False:
            # if GetAsyncKeyState ( ord('s') ) & 0x8000:


            if GetAsyncKeyState ( ord('q') ) & 0x8000:
                self.stopServer = True
                break
            elif GetAsyncKeyState ( ord('s') ) & 0x8000:
                # If 's' is pressed, acquire a single image
                self.cameraObject.grab_image_from_detector()

                # using tiff file writter, save the image contained in self.img_raw as a 16bit tiff file
                tifffile.imwrite("test_data/single_img.tiff", self.cameraObject.img_data, dtype=np.uint16)


        # This is the main loop of the server
        while self.stopServer == False:
            print("Waiting for a client to connect...")
            self.client_sock, client_address = self.listen_sock.accept()
            print('Connection established with: ', client_address)
            self.client_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8192)

            while True:
                client_request = self.client_sock.recv(12)
                request_id, exposure_time, num_frames_limit = struct.unpack('iii', client_request)
                print("request_id {}\nexposure_time {}\nnum_frames_limit {}\n".format(request_id, exposure_time,
                                                                                      num_frames_limit))
                self.cameraObject.exposure_time = exposure_time
                if request_id == self._GRAB_SINGLE_IMG_REQ_:
                    img_data = self.cameraObject.grab_image_from_detector()
                    print("Sending {}".format(img_data.reshape(-1)[:10]))
                    self.client_sock.sendall(img_data)


                elif request_id == self._GRAB_MULTIPLE_IMG_REQ_:
                    if num_frames_limit > 0:
                        self.on_grab_multiple_limited_img_request(num_frames_limit)
                    else:
                        self.on_grab_multiple_unlimited_img_request()
                else:
                    print("Invalid request code")

                if self.stopServer:
                    self.client_sock.close()
                    break
            if self.stopServer:
                break
