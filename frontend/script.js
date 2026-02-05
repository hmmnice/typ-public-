const BACKEND_URL = 'http://127.0.0.1:5000'; 
const connectionDot = document.getElementById('connectionDot');
const connectionText = document.getElementById('connectionText');

async function checkConnection() {
    try {
        const response = await fetch(`${BACKEND_URL}/ping`);
        if (response.ok) {
            connectionDot.style.backgroundColor = 'green';
            connectionText.textContent = 'Connected';
        } else {
            connectionDot.style.backgroundColor = 'red';
            connectionText.textContent = 'Disconnected';
        }
    } catch (error) {
        connectionDot.style.backgroundColor = 'red';
        connectionText.textContent = 'Disconnected';
    }
}
setInterval(checkConnection, 10000);
checkConnection();

const navRecorder = document.getElementById('navRecorder');
const navChat = document.getElementById('navChat');
const recorderSection = document.getElementById('recorderSection');
const chatSection = document.getElementById('chatSection');

navRecorder.addEventListener('click', () => {
    recorderSection.classList.remove('hidden');
    chatSection.classList.add('hidden');
});

navChat.addEventListener('click', () => {
    chatSection.classList.remove('hidden');
    recorderSection.classList.add('hidden');
    loadMeetingIds();
});

const themeToggleButton = document.getElementById('themeToggleButton');
let lightModeOn = false;

themeToggleButton.addEventListener('click', () => {
   lightModeOn = !lightModeOn;
   if (lightModeOn) {
       document.body.classList.add('light-mode');
       themeToggleButton.textContent = '𖤓';
   } else {
       document.body.classList.remove('light-mode');
       themeToggleButton.textContent = '⏾';
   }
});

let timerInterval;
let seconds = 0;
const timerDisplay = document.getElementById('timer');

function startTimer() {
   if (timerInterval) return; 

   timerDisplay.classList.add('recording');

   timerInterval = setInterval(() => {
       seconds++;
       const hours = Math.floor(seconds / 3600);
       const minutes = Math.floor((seconds % 3600) / 60);
       const secs = seconds % 60;
       timerDisplay.textContent =
           String(hours).padStart(2, '0') + ":" +
           String(minutes).padStart(2, '0') + ":" +
           String(secs).padStart(2, '0');
   }, 1000);
}

function stopTimer() {
   timerDisplay.classList.remove('recording');
   clearInterval(timerInterval);
   timerInterval = null;
   seconds = 0;
   timerDisplay.textContent = '00:00:00';

}

let mediaRecorder;
let audioChunks = [];
const recordButton = document.getElementById('recordButton');
const recordButtonOld = document.getElementById('recordButtonOld'); 
const stopButtonOld = document.getElementById('stopButtonOld'); 
const statusDiv = document.getElementById('status');
const fileInput = document.getElementById('fileInput');
const uploadButton = document.getElementById('uploadButton');
const progressDiv = document.getElementById('progressDiv');

let isRecording = false;

recordButton.addEventListener('click', async () => {

   isRecording = !isRecording;
   const selectedOption = getSelectedOption();

   if (isRecording) {

     if (selectedOption === "Just Mic") {

       try {
         const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
         audioChunks = [];
         mediaRecorder = new MediaRecorder(stream);
         mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
         mediaRecorder.onstop = handleRecordingStop;
         mediaRecorder.start();

         statusDiv.innerText = "Recording microphone...";
         recordButton.textContent = "Stop";
         recordButton.classList.add('stop');
         startTimer();

       } catch (err) {
         console.error("Error accessing microphone:", err);
         statusDiv.innerText = "Error accessing microphone. Check console for details.";
         isRecording = false;
         recordButton.textContent = "Start";
         recordButton.classList.remove('stop');
       }

     } else if (selectedOption === "Screen Audio") {

       try {
         const displayStream = await navigator.mediaDevices.getDisplayMedia({
           video: true,
           audio: true
         });
         const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });

         const audioContext = new AudioContext();
         const destination = audioContext.createMediaStreamDestination();

         if (displayStream.getAudioTracks().length > 0) {
           const systemAudioSource = audioContext.createMediaStreamSource(
             new MediaStream(displayStream.getAudioTracks())
           );
           systemAudioSource.connect(destination);
         }

         if (micStream.getAudioTracks().length > 0) {
           const micAudioSource = audioContext.createMediaStreamSource(
             new MediaStream(micStream.getAudioTracks())
           );
           micAudioSource.connect(destination);
         }

         const combinedTracks = [
           ...displayStream.getVideoTracks(),
           ...destination.stream.getAudioTracks()
         ];
         const combinedStream = new MediaStream(combinedTracks);

         audioChunks = [];
         mediaRecorder = new MediaRecorder(combinedStream);
         mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
         mediaRecorder.onstop = handleRecordingStop;
         mediaRecorder.start();

         statusDiv.innerText = "Recording screen & mic...";
         recordButton.textContent = "Stop";
         recordButton.classList.add('stop');
         startTimer();

       } catch (err) {
         console.error("Error accessing screen/microphone:", err);
         statusDiv.innerText = "Error accessing screen/microphone. Check console.";
         isRecording = false;
         recordButton.textContent = "Start";
         recordButton.classList.remove('stop');
       }

     } else {

       console.log("No valid recording option selected.");
     }

   } else {

     if (mediaRecorder && mediaRecorder.state !== "inactive") {
       mediaRecorder.stop();
     }
     recordButton.textContent = "Start";
     recordButton.classList.remove('stop');
     stopTimer();
   }
 });

async function handleRecordingStop() {
    statusDiv.innerText = "Recording stopped. Uploading...";
    const audioBlob = new Blob(audioChunks, {
        type: 'audio/wav'
    });
    try {
        const data = await sendAudioToServer(audioBlob, 'recording.wav');
        displayTranscription(data);
    } catch (err) {
        console.error('Error uploading recording:', err);
        statusDiv.innerText = "Error uploading recording. Check console.";
    }
}

document.getElementById("fileButton").addEventListener("click", function () {
   document.getElementById("fileInput").click();
});

document.getElementById("fileInput").addEventListener("change", function () {
   let fileName = this.files.length > 0 ? this.files[0].name : "No file chosen";
   document.getElementById("fileName").textContent = fileName;
   document.getElementById("uploadButton").disabled = this.files.length === 0;
});

uploadButton.addEventListener('click', async (event) => {
   event.preventDefault(); 
   if (fileInput.files.length === 0) return;
   const file = fileInput.files[0];
   statusDiv.innerText = "Uploading file. Please wait...";
   uploadButton.disabled = true;
   try {
       const data = await sendAudioToServer(file, file.name);
       displayTranscription(data);
   } catch (err) {
       console.error("Error uploading file:", err);
       statusDiv.innerText = "Error uploading file. Check console.";
   } finally {
       uploadButton.disabled = false;
   }
});

function sendAudioToServer(audioFileOrBlob, filename) {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append('file', audioFileOrBlob, filename);
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${BACKEND_URL}/transcribe`);
        xhr.upload.onprogress = event => {
            if (event.lengthComputable) {
                const percentComplete = (event.loaded / event.total) * 100;
                progressDiv.innerText = `Upload progress: ${percentComplete.toFixed(2)}%`;
            }
        };
        xhr.onload = () => {
            if (xhr.status === 200) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    resolve(response);
                } catch (parseErr) {
                    reject(new Error("Failed to parse JSON response"));
                }
            } else {
                reject(new Error(`Server returned status ${xhr.status}`));
            }
        };
        xhr.onerror = () => reject(new Error("Network error"));
        xhr.send(formData);
    });
}

function displayTranscription(data) {
    statusDiv.innerText = "Processing completed!";
    progressDiv.innerText = "Upload progress: 100%";

}

const toggleButtons = document.querySelectorAll('.toggle-btn');
toggleButtons.forEach(button => {
   button.addEventListener('click', () => {
       toggleButtons.forEach(btn => {
           btn.classList.remove('active');
           btn.setAttribute('aria-pressed', 'false');
       });
       button.classList.add('active');
       button.setAttribute('aria-pressed', 'true');

       if (getSelectedOption() === "Screen Audio") {
           console.log("Screen Audio mode activated!");

       } else if (getSelectedOption() === "Just Mic") {
           console.log("Just Mic mode activated!");

       }
   });
});

function getSelectedOption() {
   const activeButton = document.querySelector('.toggle-btn.active'); 
   return activeButton ? activeButton.textContent.trim() : null; 
}

 async function loadMeetingIds() {
   try {
       const response = await fetch(`${BACKEND_URL}/get_meeting_ids`);
       const meetings = await response.json();

       const meetingList = document.getElementById("meetingList");
       meetingList.innerHTML = ""; 

       if (meetings.length === 0) {
           console.log("No meetings found.");
           return;
       }

       meetings.forEach((meeting) => {
           const button = document.createElement("button");
           button.textContent = meeting.name;
           button.dataset.meeting = meeting.id;

           button.addEventListener("click", () => {
               document.querySelectorAll("#meetingList button").forEach(btn => btn.classList.remove("selected"));
               button.classList.add("selected");
               loadMeetingDetails(meeting.id);
           });

           meetingList.appendChild(button);
       });

   } catch (error) {
       console.error("Error loading meetings:", error);
   }
}

async function loadMeetingDetails(meetingId) {
   try {
       const response = await fetch(`${BACKEND_URL}/get_meeting/${meetingId}`);
       const data = await response.json();

       if (data.error) {
           middleContent.innerText = "Meeting transcript not found.";
           return;
       }

       transcriptContent = data.transcript || "No transcript available.";
       summaryContent = data.summary || "No summary available. [Maybe Still Generating?]";
       middleContent.innerText = transcriptContent;
       toggleButton.innerText = "Show Summary";
       isTranscriptVisible = true;

       loadChatHistory(meetingId);
   } catch (error) {
       console.error("Error loading meeting transcript:", error);
   }
}

const chatWindow = document.getElementById('chatWindow');
const chatInput = document.getElementById('chatInput');
const sendButton = document.getElementById('sendButton');
const toggleButton = document.getElementById('toggleSummaryTranscriptButton');
const middleContent = document.getElementById('middleContent');

let transcriptContent = "Transcript will appear here.";
let summaryContent = "Summary will appear here.";
let isTranscriptVisible = true;

toggleButton.addEventListener('click', () => {
    isTranscriptVisible = !isTranscriptVisible;
    if (isTranscriptVisible) {
        middleContent.innerText = transcriptContent;
        toggleButton.innerText = 'Show Summary';
    } else {
        middleContent.innerText = summaryContent;
        toggleButton.innerText = 'Show Transcript';
    }
});

sendButton.addEventListener('click', async (event) => {
   event.preventDefault(); 
   const userMessage = chatInput.value.trim();
   if (!userMessage) return;
   appendToChatWindow('user', userMessage);
   chatInput.value = '';
   try {
       const botResponse = await sendMessageToServer(userMessage);
       appendToChatWindow('bot', botResponse || "No response");
   } catch (error) {
       console.error("Chat error:", error);
       appendToChatWindow('bot', "Error communicating with server.");
   }
});

chatInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendButton.click();
    }
});

function appendToChatWindow(sender, message) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('chat-message');
    if (sender === 'user') {
        msgDiv.innerHTML = `<span class="chat-message-user">User:</span> ${message}`;
    } else {
        msgDiv.innerHTML = `<span class="chat-message-bot">Bot:</span> ${message}`;
    }
    chatWindow.appendChild(msgDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function sendMessageToServer(message) {
   const selectedMeetingId = getSelectedMeetingId();
   return new Promise((resolve, reject) => {
       const xhr = new XMLHttpRequest();
       xhr.open('POST', `${BACKEND_URL}/chat`, true);
       xhr.setRequestHeader('Content-Type', 'application/json;charset=UTF-8');
       xhr.onload = () => {
           if (xhr.status === 200) {
               try {
                   const response = JSON.parse(xhr.responseText);
                   resolve(response.reply);
               } catch (e) {
                   reject(new Error("Invalid JSON response"));
               }
           } else {
               reject(new Error(`Server returned status ${xhr.status}`));
           }
       };
       xhr.onerror = () => reject(new Error("Network error"));
       xhr.send(JSON.stringify({
           message,
           meeting_id: selectedMeetingId
       }));
   });
}

async function loadChatHistory(meetingId) {
   try {
       const response = await fetch(`${BACKEND_URL}/get_chat_history/${meetingId}`);
       const chatHistory = await response.json();

       chatWindow.innerHTML = ""; 

       chatHistory.forEach(entry => {
           appendToChatWindow('user', entry.user);
           appendToChatWindow('bot', entry.bot);
       });

   } catch (error) {
       console.error("Error loading chat history:", error);
   }
}

function getSelectedMeetingId() {
   const selectedButton = document.querySelector("#meetingList button.selected");
   return selectedButton ? selectedButton.dataset.meeting : null;
}