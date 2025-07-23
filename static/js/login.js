function loginUser() {
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;

  firebase.auth().signInWithEmailAndPassword(email, password)
    .then(async (userCredential) => {
      const idToken = await userCredential.user.getIdToken();

      const response = await fetch('/sessionLogin', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ idToken })
      });

      if (response.ok) {
        alert("Login successful!");
        window.location.href = "/dashboard";
      } else {
        const data = await response.json();
        alert("Backend session error: " + data.error);
      }
    })
    .catch((error) => {
      alert(error.message);
    });
}
window.loginUser = loginUser;
