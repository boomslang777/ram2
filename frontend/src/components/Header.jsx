import { AppBar, Toolbar, Typography, Box, Skeleton, Fade } from '@mui/material';
import { useState, useEffect, useRef, useCallback } from 'react';

function Header() {
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const [pnl, setPnl] = useState({
    totalPnL: 0,
    unrealizedPnL: 0,
    realizedPnL: 0,
    dailyPnL: 0
  });
  const [loading, setLoading] = useState(true);
  const [isConnected, setIsConnected] = useState(false);

  const updatePnL = useCallback((pnlData) => {
    if (!pnlData || typeof pnlData !== 'object') return;
    
    setPnl(prev => {
      const newPnL = {
        totalPnL: pnlData.totalPnL ?? prev.totalPnL,
        unrealizedPnL: pnlData.unrealizedPnL ?? prev.unrealizedPnL,
        realizedPnL: pnlData.realizedPnL ?? prev.realizedPnL,
        dailyPnL: pnlData.dailyPnL ?? prev.dailyPnL
      };
      
      // Only update if values have changed
      return JSON.stringify(newPnL) !== JSON.stringify(prev) ? newPnL : prev;
    });
  }, []);

  useEffect(() => {
    const connect = () => {
      try {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;
        if (wsRef.current?.readyState === WebSocket.CONNECTING) return;

        const hostname = window.location.hostname;
        const ws = new WebSocket(`ws://${hostname}/ws`);
        wsRef.current = ws;

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'data' && data.data?.pnl) {
              updatePnL(data.data.pnl);
              if (loading) setLoading(false);
            }
          } catch (error) {
            console.error('Error processing WebSocket message:', error);
          }
        };

        ws.onopen = () => {
          setIsConnected(true);
          if (loading) setLoading(false);
        };

        ws.onclose = () => {
          setIsConnected(false);
          wsRef.current = null;
          
          // Clear any existing reconnection timeout
          if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
          }
          
          // Set a new reconnection timeout
          reconnectTimeoutRef.current = setTimeout(connect, 1000);
        };

        ws.onerror = () => {
          setIsConnected(false);
        };
      } catch (error) {
        console.error('Error in connect function:', error);
      }
    };

    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [loading, updatePnL]);

  const formatPnL = useCallback((value) => {
    if (value === null || value === undefined || isNaN(value)) return '$0.00';
    return `$${Number(value).toFixed(2)}`;
  }, []);

  const getPnLColor = useCallback((value) => {
    if (value === null || value === undefined || isNaN(value)) return '#ffffff';
    const num = Number(value);
    return num >= 0 ? '#4caf50' : '#f44336';
  }, []);

  const PnLDisplay = ({ label, value, isBold = false }) => (
    <Typography 
      variant={isBold ? "h6" : "body1"} 
      sx={{ 
        fontWeight: isBold ? 'bold' : 'normal',
        minWidth: '150px',
        color: '#ffffff',
        transition: 'color 0.3s ease'
      }}
    >
      {label}:
      <span style={{ 
        color: getPnLColor(value),
        marginLeft: '8px',
        fontWeight: 'bold',
        display: 'inline-block',
        transition: 'color 0.3s ease'
      }}>
        {formatPnL(value)}
      </span>
    </Typography>
  );

  return (
    <AppBar position="static" elevation={0} sx={{ backgroundColor: '#1a1a1a' }}>
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1, color: '#ffffff' }}>
          Trading Dashboard
        </Typography>
        <Fade in={!loading} timeout={300}>
          <Box sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 3,
            minWidth: '500px',
            opacity: isConnected ? 1 : 0.7,
            transition: 'opacity 0.3s ease'
          }}>
            <PnLDisplay label="Daily P&L" value={pnl.dailyPnL} />
            <PnLDisplay label="Unrealized" value={pnl.unrealizedPnL} />
            <PnLDisplay label="Total P&L" value={pnl.totalPnL} isBold={true} />
          </Box>
        </Fade>
      </Toolbar>
    </AppBar>
  );
}

export default Header; 