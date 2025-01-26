from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, CompositeAudioClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from gtts import gTTS
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import tempfile
import time
import os
from PIL import Image, ImageFilter, ImageDraw
import io
import numpy as np
import requests
from google.cloud import storage

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Global list to track temporary files for cleanup
temp_files = []

# Use environment variables for sensitive information
GOOGLE_CREDENTIALS = os.environ.get('GOOGLE_CREDENTIALS')
if GOOGLE_CREDENTIALS:
    # Create a temporary file to store the credentials
    credentials_temp = tempfile.NamedTemporaryFile(delete=False)
    credentials_temp.write(GOOGLE_CREDENTIALS.encode())
    credentials_temp.close()
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_temp.name

# Initialize storage client
storage_client = storage.Client()
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'faketextvidgen5176')

# Update video paths to use environment variable for bucket name
BACKGROUND_VIDEOS = {
    'background': f'gs://{BUCKET_NAME}/background.mp4',
    'background_1': f'gs://{BUCKET_NAME}/background_1.mp4',
    'background_2': f'gs://{BUCKET_NAME}/background_2.mp4',
    'background_3': f'gs://{BUCKET_NAME}/background_3.mp4',
    'background_4': f'gs://{BUCKET_NAME}/background_4.mp4'
}

VOICE_SETTINGS = {
    "stability": 0.75,
    "similarity_boost": 0.45,
    "style": 0.40,
}
SOUND_EFFECTS = {
    'vineboom': os.path.join('static', 'sfx', 'vineboom.mp3'),
    'notification': os.path.join('static', 'sfx', 'notification.mp3'),
    'rizz': os.path.join('static', 'sfx', 'rizz.mp3')
}

@app.route('/')
def index():
    return render_template('index.html')

def capture_chat_interface(messages, show_header=True, header_data=None):
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--hide-scrollbars')
    chrome_options.add_argument('--force-device-scale-factor=1')
    chrome_options.add_argument('--window-size=414,900')
    
    driver = webdriver.Chrome(options=chrome_options)
    try:
        driver.get('http://127.0.0.1:5001')
        
        # Wait for elements
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "dynamic-container"))
        )
        
        # Apply header data if provided
        if header_data:
            driver.execute_script("""
                const profileImage = arguments[0];
                const headerName = arguments[1];
                
                if (profileImage) {
                    document.getElementById('profileImage').src = profileImage;
                }
                if (headerName) {
                    document.getElementById('headerName').textContent = headerName;
                }
            """, header_data['profileImage'], header_data['headerName'])
        
        # Set transparent background
        driver.execute_script("""
            document.body.style.background = 'transparent';
            document.documentElement.style.background = 'transparent';
        """)
        
        # Modified JavaScript to properly handle sound effects
        driver.execute_script("""
            const messages = arguments[0];
            const showHeader = arguments[1];
            
            // Remove input area
            const inputArea = document.querySelector('.input-area');
            if (inputArea) inputArea.remove();
            
            const container = document.querySelector('.container');
            const messageContainer = document.getElementById('messageContainer');
            const header = document.querySelector('.header');
            const dynamicContainer = messageContainer.querySelector('.dynamic-container');
            
            // Show/hide header
            if (header) {
                header.style.display = showHeader ? 'flex' : 'none';
            }
            
            // Reset container styles
            container.style.minHeight = 'unset';
            container.style.height = 'auto';
            messageContainer.style.height = 'auto';
            messageContainer.style.maxHeight = 'none';
            messageContainer.style.minHeight = 'unset';
            
            // Clear existing messages
            dynamicContainer.innerHTML = '';
            
            // Debug log messages
            console.log('Processing messages with sound effects:', messages);

            messages.forEach(msg => {
                if (msg && msg.text && msg.text.trim()) {
                    const messageDiv = document.createElement('div');
                    messageDiv.className = `message ${msg.is_sender ? 'sender' : 'receiver'}`;
                    messageDiv.textContent = msg.text.trim();
                    messageDiv.setAttribute('data-id', msg.id);
                    
                    // Add sound effect if present
                    if (msg.soundEffect) {
                        messageDiv.setAttribute('data-sound-effect', msg.soundEffect);
                        console.log(`Setting sound effect ${msg.soundEffect} for message: ${msg.text}`);
                    }
                    
                    dynamicContainer.appendChild(messageDiv);
                }
            });

            // Force layout recalculation
            container.offsetHeight;
        """, messages, show_header)
        
        # Wait for messages to render
        time.sleep(1.5)
        
        # Take screenshot
        container = driver.find_element(By.CLASS_NAME, "container")
        screenshot = container.screenshot_as_png
        image = Image.open(io.BytesIO(screenshot))
        
        # Convert to RGBA to handle transparency
        image = image.convert('RGBA')
        
        # Create a mask for rounded corners
        mask = Image.new('L', image.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([(0, 0), (image.size[0]-1, image.size[1]-1)], 20, fill=255)
        
        # Apply the mask
        output = Image.new('RGBA', image.size, (0, 0, 0, 0))
        output.paste(image, mask=mask)
        
        # Crop to content
        bbox = output.getbbox()
        if bbox:
            output = output.crop(bbox)
        
        return output
        
    except Exception as e:
        print(f"Error capturing chat interface: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        driver.quit()

def generate_audio_eleven_labs(text, voice_id, api_key):
    """Generate audio using ElevenLabs API"""
    print(f"\nGenerating audio for voice_id: {voice_id}")
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"  # Changed to v1
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": VOICE_SETTINGS
    }
    
    print("Making API request...")
    response = requests.post(url, json=data, headers=headers)
    
    if response.status_code == 200:
        temp_audio = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        temp_files.append(temp_audio.name)
        temp_audio.write(response.content)
        temp_audio.close()
        return temp_audio.name
    else:
        print(f"Error response: {response.text}")
        raise Exception(f"ElevenLabs API error: {response.text}")

def get_voice_ids(api_key):
    """Fetch and map voice IDs from ElevenLabs"""
    try:
        print("\nFetching voices from ElevenLabs...")
        voice_map = {}
        headers = {"xi-api-key": api_key}
        
        # Initialize Adam's hardcoded voice ID
        hardcoded_adam_id = 'pNInz6obpgDQGcFmaJgB'
        
        # Get regular voices
        response = requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers=headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch voices: {response.text}")
            
        voices = response.json()
        
        print("\nAvailable voices in ElevenLabs:")
        for voice in voices["voices"]:
            print(f"Name: {voice['name']}, ID: {voice['voice_id']}")
            name_lower = voice['name'].lower()
            
            # Search for Adam's voice
            if 'adam' in name_lower and 'legacy' in name_lower:
                voice_map['adam'] = voice['voice_id']
                print(f"Found Adam (Legacy) voice: {voice['name']}")
            elif 'brian' in name_lower:
                voice_map['brian'] = voice['voice_id']
                print(f"Found Brian voice: {voice['name']}")
            elif 'natalie' in name_lower:
                voice_map['natalie'] = voice['voice_id']
                print(f"Found Natalie voice: {voice['name']}")
            elif 'laura' in name_lower:
                voice_map['laura'] = voice['voice_id']
                print(f"Found Laura voice: {voice['name']}")
        
        # If Adam's voice ID is not found, use the hardcoded ID
        if 'adam' not in voice_map:
            voice_map['adam'] = hardcoded_adam_id
            print(f"Using hardcoded Adam (Legacy) voice ID: {hardcoded_adam_id}")
        
        print("\nFinal voice map:", voice_map)
        
        # Verify all required voices are found
        missing_voices = []
        required_voices = ['adam', 'brian', 'natalie', 'laura']
        for voice in required_voices:
            if voice not in voice_map:
                missing_voices.append(voice)
        
        if missing_voices:
            all_voices = "\nAll available voices:\n" + "\n".join([f"- {v['name']} ({v['voice_id']})" for v in voices["voices"]])
            raise Exception(f"Missing required voices: {', '.join(missing_voices)}.{all_voices}")
        
        return voice_map
        
    except Exception as e:
        print(f"Error fetching voice IDs: {str(e)}")
        raise

def get_background_video(video_name):
    """Download video from Google Cloud Storage"""
    try:
        if video_name not in BACKGROUND_VIDEOS:
            print(f"Invalid video name: {video_name}")
            raise ValueError(f"Invalid video name: {video_name}")
        
        # Get bucket and blob name from gs:// URL
        gs_path = BACKGROUND_VIDEOS[video_name]
        bucket_name = gs_path.split('/')[2]
        blob_name = '/'.join(gs_path.split('/')[3:])
        
        print(f"Accessing bucket: {bucket_name}, blob: {blob_name}")
        
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, f"{video_name}.mp4")
        
        print(f"Downloading to: {temp_path}")
        blob.download_to_filename(temp_path)
        return temp_path
        
    except Exception as e:
        print(f"Error in get_background_video: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

def generate_video(messages, header_data):
    try:
        voice_settings = header_data.get('voiceSettings', {})
        api_key = voice_settings.get('apiKey')
        
        if not api_key:
            raise ValueError("ElevenLabs API key is required")
            
        voice_map = get_voice_ids(api_key)
        
        if not voice_map:
            raise ValueError("No voices found in your ElevenLabs account")
        
        gender_to_voice = {
            'male': 'adam',
            'female': 'natalie'
        }
            
        sender_type = voice_settings.get('sender', 'male').lower()
        receiver_type = voice_settings.get('receiver', 'female').lower()
        
        sender_voice = gender_to_voice.get(sender_type, sender_type)
        receiver_voice = gender_to_voice.get(receiver_type, receiver_type)
        
        sender_voice_id = voice_map.get(sender_voice)
        receiver_voice_id = voice_map.get(receiver_voice)
        
        if not sender_voice_id or not receiver_voice_id:
            raise ValueError(f"Could not find voice IDs for sender ({sender_type} -> {sender_voice}) or receiver ({receiver_type} -> {receiver_voice})")
        
        selected_bg = header_data.get('backgroundVideo', 'background')
        bg_path = get_background_video(selected_bg)
        
        background = VideoFileClip(bg_path, audio=False)
        video_clips = []
        audio_clips = []
        current_time = 0
        message_count = 0

        for i in range(0, len(messages), 5):
            sequence = messages[i:i+5]
            
            for j in range(len(sequence)):
                current_window = sequence[:j+1]
                message_count += 1
                
                msg = sequence[j]
                voice_id = sender_voice_id if msg['is_sender'] else receiver_voice_id
                audio_path = generate_audio_eleven_labs(msg['text'], voice_id, api_key)
                voice_audio = AudioFileClip(audio_path)
                
                if msg.get('soundEffect') and msg['soundEffect'] in SOUND_EFFECTS:
                    effect_audio = AudioFileClip(SOUND_EFFECTS[msg['soundEffect']])
                    combined_audio = CompositeAudioClip([
                        effect_audio.with_start(0),
                        voice_audio.with_start(0.1)
                    ])
                    audio_duration = max(voice_audio.duration + 0.1, effect_audio.duration)
                else:
                    combined_audio = voice_audio
                    audio_duration = voice_audio.duration
                
                clip_duration = audio_duration + 0.09
                
                show_header = (message_count <= 5)
                current_image = capture_chat_interface(current_window, show_header=show_header, header_data=header_data)
                if current_image is None:
                    continue

                target_width = int(background.w * 0.85)
                width_scale = target_width / current_image.width
                new_height = int(current_image.height * width_scale)
                current_image = current_image.resize((target_width, new_height), Image.LANCZOS)
                current_array = np.array(current_image)

                x_center = background.w // 2 - target_width // 2
                y_top = background.h // 6

                current_clip = (ImageClip(current_array)
                                .with_duration(clip_duration)
                                .with_position((x_center, y_top)))
                
                video_clips.append(current_clip.with_start(current_time))
                audio_clips.append(combined_audio.with_start(current_time))

                current_time += clip_duration

        if not video_clips:
            raise Exception("No valid messages to generate video.")

        if current_time > background.duration:
            n_loops = int(np.ceil(current_time / background.duration))
            bg_clips = [background] * n_loops
            background_extended = concatenate_videoclips(bg_clips)
            background_extended = background_extended.subclipped(0, current_time)
        else:
            background_extended = background.subclipped(0, current_time)

        final = CompositeVideoClip(
            [background_extended] + video_clips,
            size=background_extended.size
        )

        if audio_clips:
            final = final.with_audio(CompositeAudioClip(audio_clips))

        output_path = "output_video.mp4"
        final.write_videofile(output_path, 
                            fps=30, 
                            codec='libx264',
                            audio_codec='aac',
                            bitrate="8000k",
                            preset='slower',
                            threads=4,
                            audio_bitrate="192k")
        
        return output_path
        
    except Exception as e:
        raise

@app.route('/api/generate', methods=['POST'])
def generate_endpoint():
    try:
        data = request.json
        print("Received data:", data)  # Debug log
        
        if not data or 'messages' not in data:
            return jsonify({'error': 'No messages provided'}), 400
            
        messages = data['messages']
        if not messages:
            return jsonify({'error': 'Empty messages list'}), 400
            
        # Validate voice settings
        voice_settings = data.get('voiceSettings', {})
        if not voice_settings.get('apiKey'):
            return jsonify({'error': 'ElevenLabs API key is required'}), 400
        
        if not voice_settings.get('sender') or not voice_settings.get('receiver'):
            return jsonify({'error': 'Voice settings must include sender and receiver voice types'}), 400
        
        # Debug log for messages and sound effects
        print("Processing messages in generate_endpoint:")
        for msg in messages:
            print(f"Message: {msg.get('text', 'NO TEXT')} | "
                  f"Sender: {msg.get('is_sender', 'NO SENDER')} | "
                  f"Sound Effect: {msg.get('soundEffect', 'NONE')}")
        
        header_data = {
            'profileImage': data.get('profileImage', ''),
            'headerName': data.get('headerName', 'John Doe'),
            'voiceSettings': voice_settings,
            'backgroundVideo': data.get('backgroundVideo', 'background')
        }
        
        print("Starting video generation...")  # Debug log
        video_path = generate_video(messages, header_data)
        print(f"Video generated successfully at: {video_path}")  # Debug log
        
        if not os.path.exists(video_path):
            return jsonify({'error': 'Generated video file not found'}), 500
            
        try:
            return send_file(
                video_path,
                as_attachment=True,
                download_name='generated_video.mp4',
                mimetype='video/mp4'
            )
        except Exception as e:
            print(f"Error sending file: {str(e)}")  # Debug log
            return jsonify({'error': 'Error sending video file'}), 500
            
    except Exception as e:
        print(f"Error in generate endpoint: {str(e)}")
        import traceback
        traceback.print_exc()  # Print full stack trace
        return jsonify({'error': str(e)}), 500

@app.route('/api/fetch-voices', methods=['POST'])
def fetch_voices():
    try:
        data = request.json
        api_key = data.get('apiKey')
        
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400
            
        response = requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": api_key}
        )
        
        if response.status_code != 200:
            return jsonify({'error': 'Failed to fetch voices'}), response.status_code
            
        voices = response.json()
        voice_list = [{'name': voice['name'], 'id': voice['voice_id']} 
                     for voice in voices['voices']]
                     
        return jsonify(voice_list)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Change this to use gunicorn instead of running Flask directly
    app.run(debug=True, host='0.0.0.0', port=5001) 