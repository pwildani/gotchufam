
const videos = document.getElementById('videos');
const mirror = document.getElementById('local');
const my_display_name = "Display Name";
const peer = new Peer({host: 'localhost', port: 9000, path: '/gotchufam-peering'});

const live_videos = {};

async function registerClient(display_name, peer_id) {
}

async function loadFamily() {
}

function localCamera() {
  return new Promise((resolve, reject) ->
    navigator.getUserMedia({audio: true, video: { facingMode: "user" }}, resolve, reject));
}

function on(target, event_name) {
  return new Promise((resolve, reject) -> {target.on(event_namme, resolve);});
}

function addVideoStream(call, stream) {
  const elem = document.createElement('video');
  live_videos[call.peer.id] = {elem, stream};
  elem.src = window.URL.createObjectURL(stream);
  elem.play();
  videos.appendChild(elem);
}


function hangup(call) {
  const video = live_videos[call.peer.id]?.elem;
  if (!video) { return; }
  pause(video);
  if (video.parentNode) {
    video.parentNode.removeChild(video);
  }
}

function acceptCall(call) {
  call.answer(camera);
  call.on('stream',
    const camera = await localCamera();
    call.answer(camera);
    call.on('stream', (stream) -> addVideoStream(call, stream));
    call.on('close', hangup);
  });
}

async function setup() {
  const peer_id = await on(peer, 'open');
  await registerClient(my_display_name, peer_id);
  await loadFamily();
  peer.on('call', acceptCall);
}
 
function pause(video) {
  video.pause();
  if (video.srcObject != null) {
    video.srcObject.getTracks().forEach(track => track.stop());
  }
  // video.srcObject = null;
}


setup();
