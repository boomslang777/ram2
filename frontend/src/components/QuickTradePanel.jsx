import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
} from '@mui/material';
import { useState } from 'react';
import { useMutation, useQueryClient, useQuery } from 'react-query';
import { api } from '../services/api';

function QuickTradePanel() {
  const queryClient = useQueryClient();
  const [instrument, setInstrument] = useState('SPY');
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState(null);

  // Get settings and SPY price
  const { data: settings } = useQuery('settings', api.getSettings);
  const { data: spyPriceData } = useQuery('spy-price', api.getSpyPrice, {
    refetchInterval: 5000
  });

  const placeBuyMutation = useMutation(
    (data) => api.quickTrade(data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('positions');
        queryClient.invalidateQueries('orders');
        setError(null);
      },
      onError: (error) => {
        setError(error.response?.data?.detail || 'Failed to place buy order');
      }
    }
  );

  const placeSellMutation = useMutation(
    (data) => api.quickTrade(data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('positions');
        queryClient.invalidateQueries('orders');
        setError(null);
      },
      onError: (error) => {
        setError(error.response?.data?.detail || 'Failed to place sell order');
      }
    }
  );

  const createSignal = (isBuy) => {
    if (instrument === 'SPY') {
      return {
        action: isBuy ? 'Buy Call' : 'Buy Put',
        instrument: 'SPY',
        symbol: 'SPY',
        quantity: quantity,
        type: 'OPTION'
      };
    } else {
      return {
        action: isBuy ? 'Buy MES' : 'Short MES',
        instrument: 'MES',
        symbol: 'MES',
        quantity: quantity,
        type: 'FUTURES'
      };
    }
  };

  const handleBuy = async () => {
    if (!settings?.trading_enabled) {
      setError('Trading is currently disabled');
      return;
    }
    
    try {
      const signal = createSignal(true);
      console.log('Sending buy signal:', signal);  // Debug log
      await placeBuyMutation.mutateAsync(signal);
    } catch (error) {
      console.error('Buy error:', error);
    }
  };

  const handleSell = async () => {
    if (!settings?.trading_enabled) {
      setError('Trading is currently disabled');
      return;
    }
    
    try {
      const signal = createSignal(false);
      console.log('Sending sell signal:', signal);  // Debug log
      await placeSellMutation.mutateAsync(signal);
    } catch (error) {
      console.error('Sell error:', error);
    }
  };

  // Set default quantity when instrument changes
  const handleInstrumentChange = (e) => {
    const newInstrument = e.target.value;
    setInstrument(newInstrument);
    if (settings) {
      setQuantity(newInstrument === 'SPY' ? settings.spy_quantity : settings.mes_quantity);
    }
  };

  if (!settings) return null;

  return (
    <Box sx={{ mb: 4 }}>
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Quick Trade
          </Typography>
          
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={3}>
              <FormControl fullWidth>
                <InputLabel>Instrument</InputLabel>
                <Select
                  value={instrument}
                  onChange={handleInstrumentChange}
                  label="Instrument"
                >
                  <MenuItem value="SPY">SPY Options</MenuItem>
                  <MenuItem value="MES">MES Futures</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={3}>
              <TextField
                fullWidth
                type="number"
                label="Quantity"
                value={quantity}
                onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                InputProps={{ inputProps: { min: 1 } }}
              />
            </Grid>
            
            <Grid item xs={12} sm={3}>
              <Button
                fullWidth
                variant="contained"
                color="success"
                onClick={handleBuy}
                disabled={placeBuyMutation.isLoading || !settings.trading_enabled}
              >
                {instrument === 'SPY' ? 'Buy Call' : 'Buy MES'}
              </Button>
            </Grid>
            
            <Grid item xs={12} sm={3}>
              <Button
                fullWidth
                variant="contained"
                color="error"
                onClick={handleSell}
                disabled={placeSellMutation.isLoading || !settings.trading_enabled}
              >
                {instrument === 'SPY' ? 'Buy Put' : 'Short MES'}
              </Button>
            </Grid>
          </Grid>

          {!settings.trading_enabled && (
            <Box sx={{ mt: 2 }}>
              <Alert severity="warning">Trading is currently disabled</Alert>
            </Box>
          )}

          {error && (
            <Box sx={{ mt: 2 }}>
              <Alert severity="error">{error}</Alert>
            </Box>
          )}

          {instrument === 'SPY' && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" color="textSecondary">
                Using {settings.dte === 0 ? '0 DTE (Today)' : '1 DTE (Tomorrow)'} options • 
                {settings.call_strike_selection} Calls / {settings.put_strike_selection} Puts
                {spyPriceData?.price && ` • Current SPY: $${spyPriceData.price.toFixed(2)}`}
              </Typography>
            </Box>
          )}

          {instrument === 'MES' && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" color="textSecondary">
                MES Futures
              </Typography>
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}

export default QuickTradePanel; 