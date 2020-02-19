let videos = document.getElementById('videos');
let mirror = document.getElementById('local');
let online_view = document.getElementById('facebar');
let my_display_name = "Display Name";
let peer = new Peer({...PEER_JS_CONFIG, path: '/gotchufam-peering'});

let family = {};

// Elements playing a remote video stream, by peer id
let live_videos = {};

// Connection: Data message exchange, by peer id.
let connections = {};

// Call media stream exchange, by peer id.
let calls = {};

let online = {}
let heartbeat_loop = null;


function keys(obj) {
  let out = [];
  for (let key in obj) {
    out.push(key);
  }
  return out;
}

function compose_api_url(path, url_params) {
  let url = new URL(API_ROOT + path, window.location.href);
  if (url_params) {
    for (let key in url_params) {
      url.searchParams.set(key, url_params[key]);
    }
  }
  return url;
}

async function parse_api_response(response) {
  if (!response.ok) {
    throw new Error("network error: " + response.status_code);
  }
  let json = await response.json();
  if (json.status != "ok") {
    throw new Error("server error: " + json.status);
  }
  return {response, json};
}

async function api_call(methodname, url_params, body, init) {
  let url = compose_api_url(methodname, url_params);

  if(body !== null && typeof(body) == "object") {
    let form = new FormData();
    for (let key in body) {
      form.set(key, body[key]);
    }
    body = form;
  }
  if (body === null) {
    body = undefined;
  }

  let response = await fetch(url, {body, ...init});
  return parse_api_response(response);
}

async function api_fetch(url, params, init) {
  return api_call(url, params, null, {...init, method:'GET'});
}

async function api_post(url, params, body, init) {
  return api_call(url, params, body, {...init, method:'POST'});
}


async function ensureConnection(peer_id) {
  if (live_videos[peer_id]) {
    // TODO: health checks on peer data connection and video stream.
    return;
  }

  if (!connections[peer_id]) {
    connections[peer_id] = peer.connect(peer_id);
  }

  let call_initiator = false;
  if (!calls[peer_id]) {
      let localstream = await camera;
      calls[peer_id] = peer.call(peer_id, localstream);
      call_initiator = true;
  }

  // TODO: actually wire up the video
  let call = calls[peer_id];
  if (!call_initiator) {
    camera.then(function(localstream) {
      call.answer(localstream);
      call.on('stream', function(remotestream) { addVideoStream(call, remotestream); });
    });
  }
  call.on('close', hangup);
}

async function runHeartbeat() {
  let response = await api_post('heartbeat', {}, {client_id: peer.id});
  online = response.json.online;
  let missing_calls = [];
  for (let member of online) {
    ensureConnection(member.client_id);

    // Debug code
    let div = document.createElement('div')
    div.innerText = member.display_name;
    console.log('Online:', member);
    online_view.appendChild(div);
  }
  return online;
}

function registerAsOnline() {
  runHeartbeat();
  heartbeat = setInterval(runHeartbeat, 30000)
}


async function loadFamily() {
  let response = await api_fetch('whoswho');
  family = response.json.family;
  return family;
}

function make_promise() {
  let resolve, reject;
  let p = new Promise(function (ok, err) {return {resolve: ok, reject: err}; });
  return {resolve: resolve, reject: reject, promise: promise};
}

function localCamera() {
  return new Promise(function (resolve, reject) {
    navigator.getUserMedia({audio: true, video: { facingMode: "user" }}, resolve, reject);
  });
}
let camera = localCamera();
camera.then(function(stream) {
  mirror.srcObject = stream;
  mirror.play();
});

function on(target, event_name) {
  return new Promise(function (resolve, reject) {target.on(event_name, resolve);});
}

function addVideoStream(call, stream) {
  let elem = document.createElement('video');
  live_videos[call.peer.id] = {elem, stream};
  elem.src = window.URL.createObjectURL(stream);
  elem.play();
  videos.appendChild(elem);
  return elem;
}


function hangup(call) {

  // Shut down video player.
  if (live_videos[call.peer.id]) {
    let video = live_videos[call.peer.id].elem;
    if (video) {
      pause(video);
      if (video.parentNode) {
        video.parentNode.removeChild(video);
      }
    }
  }

  // Shut down media connection
  if (calls[call.peer.id]) {
    calls[call.peer.id].close();
  }
  calls[call.peer.id] = null;

  // Shut down data connection
  if (connections[call.peer.id]) {
    connections[call.peer.id].destroy();
  }
  connections[call.peer.id] = null;
}

function acceptCall(call) {
  calls[call.peer.id] = call;
  ensureConnection(call.peer_id);
}

async function setup() {
  let peer_id = await on(peer, 'open');
  registerAsOnline(peer_id);
  loadFamily();
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

