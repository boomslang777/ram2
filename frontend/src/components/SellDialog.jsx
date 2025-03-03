import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  CircularProgress,
  Alert
} from '@mui/material';
import { useState } from 'react';

function SellDialog({ open, onClose, onSubmit, position, isLoading }) {
  const [quantity, setQuantity] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = () => {
    const qty = parseInt(quantity);
    if (isNaN(qty) || qty <= 0) {
      setError('Please enter a valid quantity');
      return;
    }

    // For SPY options, can't sell more than current position
    if (position?.contract?.secType === 'OPT' && qty > Math.abs(position?.position || 0)) {
      setError('Sell quantity cannot exceed current position size for options');
      return;
    }

    // For MES futures, no quantity restriction (can go short)
    onSubmit(qty);
    setQuantity('');
    setError('');
  };

  const isSPYOption = position?.contract?.secType === 'OPT';
  const isMESFuture = position?.contract?.symbol === 'MES';

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>
        Sell {position?.contract?.localSymbol}
        {isMESFuture && " (Can go short)"}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 2 }}>
          {isMESFuture && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Futures positions can be sold short. Negative quantity indicates short position.
            </Alert>
          )}
          <TextField
            autoFocus
            label="Quantity"
            type="number"
            fullWidth
            value={quantity}
            onChange={(e) => {
              setQuantity(e.target.value);
              setError('');
            }}
            error={!!error}
            helperText={error}
            disabled={isLoading}
            inputProps={isSPYOption ? {
              max: Math.abs(position?.position || 0)
            } : {}}
          />
          {position && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              Current Position: {position.position}
              {isSPYOption && ` (Max sell: ${Math.abs(position.position)})`}
            </Typography>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isLoading}>
          Cancel
        </Button>
        <Button 
          onClick={handleSubmit} 
          variant="contained" 
          color="error"
          disabled={isLoading}
        >
          {isLoading ? <CircularProgress size={24} /> : 'Sell'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default SellDialog; 