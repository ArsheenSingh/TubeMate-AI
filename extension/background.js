// background.js
chrome.action.onClicked.addListener((tab) => {
  if (!tab.url || !tab.url.startsWith('https://www.youtube.com/watch')) return;
  chrome.scripting.insertCSS({
    target: { tabId: tab.id },
    files: ['style.css']
  });
  chrome.scripting.executeScript({
    target: { tabId: tab.id },
    files: ['content.js']
  });
});
