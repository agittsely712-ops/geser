self.addEventListener('install', event => { self.skipWaiting(); });
self.addEventListener('activate', event => { event.waitUntil(self.clients.claim()); });
self.addEventListener('notificationclick', event => {
 event.notification.close();
 const target = new URL('GESER_AI_DUA_HP.html', self.registration.scope).href;
 event.waitUntil(self.clients.matchAll({type:'window',includeUncontrolled:true}).then(windows => {
  const match=windows.find(w=>w.url.split('?')[0]===target);
  if(match)return match.focus();
  return self.clients.openWindow(target);
 }));
});
