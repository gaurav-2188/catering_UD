import axios from "axios";

const api = axios.create({
  // This uses your production backend URL when deployed, or falls back to local testing
  baseURL: process.env.REACT_APP_API_URL || "http://localhost:8000/api",
});

// Automatically inject your auth token into headers if it exists
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("ud_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
