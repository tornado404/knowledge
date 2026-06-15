/* PKOS Clip Popup Logic */

document.addEventListener('DOMContentLoaded', function () {
  const btnReadUrl = document.getElementById('btn-read-url');
  const urlDisplay = document.getElementById('url-display');
  const urlText = document.getElementById('url-text');
  const pageTitle = document.getElementById('page-title');

  btnReadUrl.addEventListener('click', function () {
    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      if (tabs.length === 0) {
        urlText.textContent = '无法获取当前页面';
        pageTitle.textContent = '';
        urlDisplay.classList.remove('hidden');
        return;
      }

      const tab = tabs[0];
      urlText.textContent = tab.url || '';
      pageTitle.textContent = tab.title || '';
      urlDisplay.classList.remove('hidden');
    });
  });
});
