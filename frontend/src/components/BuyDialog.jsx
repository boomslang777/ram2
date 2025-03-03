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

function BuyDialog({ open, onClose, onSubmit, position, isLoading }) {
  const [quantity, setQuantity] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = () => {
    const qty = parseInt(quantity);
    if (isNaN(qty) || qty <= 0) {
      setError('Please enter a valid quantity');
      return;
    }
    onSubmit(qty);
    setQuantity('');
    setError('');
  };

  const isSPYOption = position?.contract?.secType === 'OPT';
  const isMESFuture = position?.contract?.symbol === 'MES';
  const isShortMES = isMESFuture && position?.position < 0;

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>
        {isShortMES ? 'Cover' : 'Buy'} {position?.contract?.localSymbol}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 2 }}>
          {isMESFuture && (
            <Alert severity="info" sx={{ mb: 2 }}>
              {isShortMES 
                ? 'Buying will reduce your short position'
                : 'You can buy to open a new long position or cover an existing short position'}
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
          />
          {position && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              Current Position: {position.position}
              {isShortMES && ` (Max cover: ${Math.abs(position.position)})`}
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
          color="primary"
          disabled={isLoading}
        >
          {isLoading ? <CircularProgress size={24} /> : (isShortMES ? 'Cover' : 'Buy')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default BuyDialog; 