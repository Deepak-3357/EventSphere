const apiStatusButton = document.querySelector("#apiStatusButton");
const apiStatus = document.querySelector("#apiStatus");

apiStatusButton?.addEventListener("click", async () => {
  apiStatus.textContent = "Checking the EventSphere API…";

  try {
    const response = await fetch(apiUrl("/api/health"));
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    apiStatus.textContent = `${data.service}: ${data.status}`;
  } catch (error) {
    apiStatus.textContent = "API is not running locally yet. Start the Flask backend to connect.";
  }
});
