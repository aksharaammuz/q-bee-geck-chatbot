
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const messages = document.getElementById("messages");
const language = document.getElementById("language");

function escapeHTML(str){
  return str.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

function addMessage(text, role, meta="", lang="en"){
  const wrap = document.createElement("div");
  wrap.className = `message ${role}`;
  wrap.innerHTML = `
    <div>
      <div class="bubble">${escapeHTML(text).replace(/\n/g, "<br>")}</div>
      ${role === "bot" ? `<button class="voice-btn" type="button">🔊 Listen</button>` : ""}
      ${meta ? `<div class="meta">${escapeHTML(meta)}</div>` : ""}
    </div>`;
  if(role === "bot"){
    wrap.querySelector(".voice-btn").addEventListener("click", () => playVoice(text, lang, wrap.querySelector(".voice-btn")));
  }
  messages.appendChild(wrap);
  messages.scrollTop = messages.scrollHeight;
}

function addTyping(){
  const wrap = document.createElement("div");
  wrap.className = "message bot";
  wrap.id = "typing";
  wrap.innerHTML = `<div class="bubble"><span class="typing"><b></b><b></b><b></b></span></div>`;
  messages.appendChild(wrap);
  messages.scrollTop = messages.scrollHeight;
}

async function ask(text){
  text = text.trim();
  if(!text) return;
  addMessage(text, "user");
  input.value = "";
  autoResize();
  addTyping();

  try{
    const res = await fetch("/api/chat", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({message:text, language:language.value})
    });
    const data = await res.json();
    document.getElementById("typing")?.remove();
    if(!res.ok) throw new Error(data.error || "Request failed");
    addMessage(data.answer, "bot", "", data.language);
  }catch(err){
    document.getElementById("typing")?.remove();
    addMessage("Sorry, I couldn't process that request. Please try again.", "bot");
  }
}

let currentAudio = null;
let currentButton = null;

async function playVoice(text, lang, btn) {
  // If this button is currently playing, stop it
  if (currentAudio && currentButton === btn) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    currentAudio = null;
    btn.textContent = "🔊 Listen";
    btn.disabled = false;
    currentButton = null;
    return;
  }

  // Stop any other audio
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
  }

  if (currentButton) {
    currentButton.textContent = "🔊 Listen";
    currentButton.disabled = false;
  }

  const old = btn.textContent;
  btn.textContent = "⏳ Generating voice...";
  btn.disabled = true;

  try {
    const res = await fetch("/api/tts", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text, language: lang})
    });

    const data = await res.json();

    if (!res.ok) throw new Error(data.error || "TTS failed");

    const audio = new Audio(data.audio_url);

    currentAudio = audio;
    currentButton = btn;

    btn.disabled = false;
    btn.textContent = "⏸ Pause";

    audio.onended = () => {
      btn.textContent = old;
      btn.disabled = false;
      currentAudio = null;
      currentButton = null;
    };

    await audio.play();

  } catch (err) {
    if ("speechSynthesis" in window) {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = lang === "ml" ? "ml-IN" : "en-IN";

      speechSynthesis.cancel();
      speechSynthesis.speak(u);
    }

    btn.textContent = old;
    btn.disabled = false;
    currentAudio = null;
    currentButton = null;
  }
}

form.addEventListener("submit", e => {e.preventDefault(); ask(input.value);});
input.addEventListener("keydown", e => {
  if(e.key === "Enter" && !e.shiftKey){e.preventDefault(); form.requestSubmit();}
});
function autoResize(){input.style.height="auto";input.style.height=Math.min(input.scrollHeight,130)+"px";}
input.addEventListener("input", autoResize);
document.querySelectorAll(".quick button").forEach(b => b.addEventListener("click", () => ask(b.dataset.q)));
