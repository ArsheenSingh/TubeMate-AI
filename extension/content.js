// Updated content.js with improved handling for long videos
(function(){
  if(document.getElementById('tubemate-chat')) return;
  const VIDEO_ID = new URLSearchParams(window.location.search).get('v');
  if(!VIDEO_ID) return;
  
  const chat = document.createElement('div');
  chat.id='tubemate-chat';
  chat.innerHTML=`
    <div id="tubemate-header">
      <div class="logo-container">
        <div class="logo-icon">
          <svg viewBox="0 0 24 24" width="18" height="18">
            <path d="M9 16.5l7-4.5-7-4.5v9z" fill="#00FFBB"/>
          </svg>
        </div>
        TubeMate AI
      </div>
      <div class="close-button"></div>
    </div>
    <div class="messages"></div>
    <div class="input-container">
      <input placeholder="Type your question..." />
      <button></button>
    </div>`;
  
  document.body.appendChild(chat);
  
  const messagesEl=chat.querySelector('.messages'),
        inputEl=chat.querySelector('input'),
        btn=chat.querySelector('button'),
        closeBtn=chat.querySelector('.close-button');
  
  // Add close functionality
  closeBtn.addEventListener('click', () => {
    chat.style.opacity = '0';
    setTimeout(() => chat.remove(), 300);
  });
  
  chrome.storage.local.get([VIDEO_ID],({[VIDEO_ID]:hist})=>{
    if(!hist){
      appendMessage('assistant','Hi, I am your assistant, ask me anything about the video.');
      chrome.storage.local.set({[VIDEO_ID]:[{role:'assistant',text:'Hi, I am your assistant, ask me anything about the video.'}]});
    } else { hist.forEach(m=>appendMessage(m.role,m.text)); }
  });
  
  function appendMessage(role,text){
    const d=document.createElement('div');
    d.classList.add('message',role);
    d.textContent=text;
    messagesEl.appendChild(d);
    messagesEl.scrollTop=messagesEl.scrollHeight;
  }
  
  function showSpinner(){
    const spinner=document.createElement('div');
    spinner.className='spinner';
    spinner.id='loading-spinner';
    spinner.innerHTML=`<div class="dot"></div><div class="dot"></div><div class="dot"></div>`;
    messagesEl.appendChild(spinner);
    messagesEl.scrollTop=messagesEl.scrollHeight;
  }
  
  function removeSpinner(){
    const s=document.getElementById('loading-spinner'); 
    if(s) s.remove();
  }
  
  // Store active queries for polling
  let activeQueries = {};
  let pollingInterval = null;
  
  function startPolling() {
    if (pollingInterval) return; // Already polling
    
    pollingInterval = setInterval(() => {
      // Check all active queries
      Object.keys(activeQueries).forEach(queryKey => {
        const queryData = activeQueries[queryKey];
        
        // If this query has been active for more than 2 minutes, remove it
        if (Date.now() - queryData.timestamp > 120000) { // 2 minutes
          delete activeQueries[queryKey];
          return;
        }
        
        // Poll for results
        fetch(`http://localhost:5000/check_result?videoId=${queryData.videoId}&query=${encodeURIComponent(queryData.query)}`)
          .then(r => r.json())
          .then(data => {
            if (data.found) {
              // We got a result!
              const msgId = queryData.messageId;
              const existingMsg = document.getElementById(msgId);
              
              if (existingMsg) {
                // Update existing message
                existingMsg.textContent = data.answer;
                
                // Update in storage
                chrome.storage.local.get([VIDEO_ID], ({[VIDEO_ID]:h=[]}) => {
                  // Find and update the message
                  const updatedHistory = h.map(msg => {
                    if (msg.id === msgId) {
                      return {...msg, text: data.answer};
                    }
                    return msg;
                  });
                  chrome.storage.local.set({[VIDEO_ID]: updatedHistory});
                });
                
                // Remove from active queries
                delete activeQueries[queryKey];
              }
            }
          })
          .catch(e => {
            console.error('Error checking results:', e);
          });
      });
      
      // If no more active queries, stop polling
      if (Object.keys(activeQueries).length === 0) {
        clearInterval(pollingInterval);
        pollingInterval = null;
      }
    }, 5000); // Check every 5 seconds
  }
  
  function sendQuery(){
    const q=inputEl.value.trim(); 
    if(!q) return; 
    inputEl.value=''; 
    appendMessage('user',q);
    
    // Generate a unique ID for this message
    const messageId = 'msg_' + Date.now();
    
    chrome.storage.local.get([VIDEO_ID],({[VIDEO_ID]:h=[]})=>{
      h.push({role:'user', text:q});
      chrome.storage.local.set({[VIDEO_ID]:h});
    });
    
    showSpinner();
    fetch('http://localhost:5000/query',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({videoId:VIDEO_ID,query:q})
    })
      .then(r=>r.json())
      .then(d=>{
        removeSpinner();
        const a=d.answer||d.error||'No response';
        
        // Create message with ID for potential updates
        const msgEl = document.createElement('div');
        msgEl.classList.add('message', 'assistant');
        msgEl.id = messageId;
        msgEl.textContent = a;
        messagesEl.appendChild(msgEl);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        
        // Store in history
        chrome.storage.local.get([VIDEO_ID],({[VIDEO_ID]:h=[]})=>{
          h.push({role:'assistant', text:a, id: messageId});
          chrome.storage.local.set({[VIDEO_ID]:h});
        });
        
        // If this is a processing message, add to active queries for polling
        if(a.includes("analyzing this long video")) {
          // Add to active queries
          activeQueries[`${VIDEO_ID}:${q}`] = {
            videoId: VIDEO_ID,
            query: q, 
            messageId: messageId,
            timestamp: Date.now()
          };
          
          // Start polling
          startPolling();
        }
      })
      .catch(e=>{
        removeSpinner();
        appendMessage('assistant','Error: '+e.message);
      });
  }
  
  btn.addEventListener('click',sendQuery);
  inputEl.addEventListener('keypress',e=>{if(e.key==='Enter')sendQuery();});
})();