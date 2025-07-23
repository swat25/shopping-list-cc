function registerUser() {
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;
  const confirmPassword = document.getElementById("confirm_password").value;

  if (password !== confirmPassword) {
    alert("Passwords do not match");
    return;
  }

  firebase.auth().createUserWithEmailAndPassword(email, password)
    .then(async (userCredential) => {
      // Get Firebase ID token
      const idToken = await userCredential.user.getIdToken();

      // Send token to backend to create session
      const response = await fetch('/sessionLogin', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ idToken })
      });

      if (response.ok) {
        alert("Registered successfully");
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
window.registerUser = registerUser;
