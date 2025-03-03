import axios from 'axios';

const BASE_URL = '';

export const api = {
  getSettings: async () => {
    const response = await axios.get(`${BASE_URL}/api/settings`);
    return response.data;
  },
  
  updateSettings: async (settings) => {
    const response = await axios.post(`${BASE_URL}/api/settings`, settings);
    return response.data;
  },
  
  getPositions: async () => {
    const response = await axios.get(`${BASE_URL}/api/positions`);
    return response.data;
  },
  
  getOrders: async () => {
    const response = await axios.get(`${BASE_URL}/api/orders`);
    return response.data;
  },
  
  closePosition: async (data) => {
    const response = await axios.post(`${BASE_URL}/api/close-position`, data);
    return response.data;
  },
  
  cancelOrder: async (data) => {
    const response = await axios.post(`${BASE_URL}/api/cancel-order`, data);
    return response.data;
  },
  
  getSpyPrice: async () => {
    const response = await axios.get(`${BASE_URL}/api/spy-price`);
    return response.data;
  },

  sendSignal: async (signal) => {
    const response = await axios.post(`${BASE_URL}/api/signal`, signal);
    return response.data;
  },

  quickTrade: async (signal) => {
    const response = await axios.post(`${BASE_URL}/api/quick-trade`, signal);
    return response.data;
  },

  placeBuyOrder: async (data) => {
    const response = await axios.post('/api/signal', {
      ...data,
      action: 'BUY'
    });
    return response.data;
  },

  placeSellOrder: async (data) => {
    const response = await axios.post('/api/signal', {
      ...data,
      action: 'SELL'
    });
    return response.data;
  },

  async post(endpoint, data) {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'An error occurred');
    }
    
    return response.json();
  }
}; 