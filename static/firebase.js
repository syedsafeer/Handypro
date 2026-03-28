
// Firebase Configuration
const firebaseConfig = {
    apiKey: "Your API Key",
    authDomain: "windturbine-5b07e.firebaseapp.com",
    projectId: "https://windturbine-5b07e-default-rtdb.firebaseio.com/",
    storageBucket: "windturbine-5b07e.appspot.com",
    messagingSenderId: "394655219800",
    appId: "1:394655219800:web:d6b4b550a3d1f0c5690a2d"
};
firebase.initializeApp(firebaseConfig);
const db = firebase.firestore();
const auth = firebase.auth();
