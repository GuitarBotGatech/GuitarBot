import wave
import pyaudio
import math
import time

class inputAudio:
    def __init__(self, chunks=2048, format=pyaudio.paInt16, channels=1, rate=44100, recordTime=12, waveName='output.mp3'):
        self.paudio = pyaudio.PyAudio()
        self.info = self.paudio.get_host_api_info_by_index(0)
        for i in range(0, self.info.get('deviceCount')):
            if (self.paudio.get_device_info_by_host_api_device_index(0,i).get("maxInputChannels")) > 0:
                print("Input Device ID: ",  i, ", ", self.paudio.get_device_info_by_host_api_device_index(0,i).get("name"))
        index = int(input())
        self.stream = self.paudio.open(format=format, channels=channels, rate=rate, input=True, input_device_index=index, frames_per_buffer=chunks)
        self.frames = []
        self.rate = rate
        self.chunks = chunks
        self.channels = channels
        self.format = format
        self.recordTime = recordTime
        self.waveName = waveName

    def start(self):
        print("Recording starting!")
        timer = 3
        while(timer >= 0):
            if(timer == 0):
                print("GO!")
                timer -= 1
            else:
                print(timer)
                timer -= 1
                time.sleep(1)

        for i in range(0, math.ceil(self.rate / self.chunks * self.recordTime)):
            data = self.stream.read(self.chunks)
            self.frames.append(data)
        print("Recording Finished!")
        self.stream.stop_stream()
        self.stream.close()
        self.paudio.terminate()

    def stop(self):
        self.stream.stop_stream()

    def reset(self):
        self.stop()
        if self.stream:
            self.stream.close()
        self.paudio.terminate()
    
    def outputWav(self):
        with wave.open(self.waveName, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.paudio.get_sample_size(self.format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(self.frames))
        print(f"Audio saved as {self.outputWav}")

    
# CHUNK = 1024
# FORMAT = pyaudio.paInt16
# CHANNELS = 1
# RATE = 44100
# RECORD_SECONDS = 10
# WAVE_OUTPUT_FILENAME = "output.wav"
# audio = pyaudio.PyAudio()

# print("Record Device List:")
# info = audio.get_host_api_info_by_index(0)
# numdevices = info.get('deviceCount')
# for i in range(0, numdevices):
#     if (audio.get_device_info_by_host_api_device_index(0,i).get("maxInputChannels")) > 0:
#         print("Input Device ID: ",  i, ", ", audio.get_device_info_by_host_api_device_index(0,i).get("name"))
# index = int(input())
# print("Recording with: "+str(index))
# stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, input_device_index=index, frames_per_buffer=CHUNK)
# print("Recording...")
# Recordframes = []
# for i in range(0, math.ceil(RATE / CHUNK * RECORD_SECONDS)):
#     data = stream.read(CHUNK)
#     Recordframes.append(data)
# print("Recording Finished!")
# stream.stop_stream()
# stream.close()
# audio.terminate()


# with wave.open(WAVE_OUTPUT_FILENAME, 'wb') as wf:
#     wf.setnchannels(CHANNELS)
#     wf.setsampwidth(audio.get_sample_size(FORMAT))
#     wf.setframerate(RATE)
#     wf.writeframes(b''.join(Recordframes))
# print(f"Audio saved as {WAVE_OUTPUT_FILENAME}")