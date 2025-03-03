import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Button,
  Typography,
  Box,
  CircularProgress,
  Tooltip,
  Stack
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { api } from '../services/api';
import { useEffect, useState } from 'react';
import BuyDialog from './BuyDialog';
import SellDialog from './SellDialog';

function PositionsTable() {
  const queryClient = useQueryClient();
  const [localPositions, setLocalPositions] = useState([]);
  const [buyDialogOpen, setBuyDialogOpen] = useState(false);
  const [sellDialogOpen, setSellDialogOpen] = useState(false);
  const [selectedPosition, setSelectedPosition] = useState(null);

  // WebSocket data subscription
  useEffect(() => {
    const ws = new WebSocket(`ws://${window.location.hostname}/ws`);
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'data' && Array.isArray(data.data?.positions)) {
          setLocalPositions(data.data.positions);
        }
      } catch (error) {
        console.error('Error processing WebSocket message:', error);
      }
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, []);

  const closeMutation = useMutation(
    (positionId) => api.closePosition({ position_id: Number(positionId) }),
    {
      onSuccess: () => queryClient.invalidateQueries('positions')
    }
  );

  const buyMutation = useMutation(
    ({ positionId, quantity }) => 
      api.post(`/api/positions/${positionId}/buy`, { position_id: positionId, quantity }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('positions');
        setBuyDialogOpen(false);
      }
    }
  );

  const sellMutation = useMutation(
    ({ positionId, quantity }) => 
      api.post(`/api/positions/${positionId}/sell`, { position_id: positionId, quantity }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('positions');
        setSellDialogOpen(false);
      }
    }
  );

  const handleBuyClick = (position) => {
    setSelectedPosition(position);
    setBuyDialogOpen(true);
  };

  const handleSellClick = (position) => {
    setSelectedPosition(position);
    setSellDialogOpen(true);
  };

  const handleBuySubmit = (quantity) => {
    if (selectedPosition) {
      buyMutation.mutate({
        positionId: selectedPosition.contract.conId,
        quantity
      });
    }
  };

  const handleSellSubmit = (quantity) => {
    if (selectedPosition) {
      sellMutation.mutate({
        positionId: selectedPosition.contract.conId,
        quantity
      });
    }
  };

  // Use WebSocket data instead of polling
  const positions = localPositions;
  
  if (!positions || positions.length === 0) {
    return (
      <Box>
        <Typography variant="h6" gutterBottom>
          Open Positions
        </Typography>
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Symbol</TableCell>
                <TableCell align="right">Quantity</TableCell>
                <TableCell align="right">Average Cost</TableCell>
                <TableCell align="right">Market Price</TableCell>
                <TableCell align="right">Unrealized P&L</TableCell>
                <TableCell align="right">Daily P&L</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              <TableRow>
                <TableCell colSpan={7} align="center">
                  No open positions
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Open Positions
      </Typography>
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Symbol</TableCell>
              <TableCell align="right">Quantity</TableCell>
              <TableCell align="right">Average Cost</TableCell>
              <TableCell align="right">Market Price</TableCell>
              <TableCell align="right">Unrealized P&L</TableCell>
              <TableCell align="right">Daily P&L</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {positions.map((position) => (
              <TableRow key={position.contract.conId}>
                <TableCell>
                  <Tooltip title={`${position.contract.symbol} ${position.contract.secType}`}>
                    <span>{position.contract.localSymbol}</span>
                  </Tooltip>
                </TableCell>
                <TableCell align="right">{position.position}</TableCell>
                <TableCell align="right">${(position.avgCost / (position.contract.multiplier || 1)).toFixed(2)}</TableCell>
                <TableCell align="right">${position.marketPrice.toFixed(2)}</TableCell>
                <TableCell 
                  align="right"
                  sx={{ 
                    color: position.unrealizedPNL >= 0 ? 'success.main' : 'error.main',
                    fontWeight: 'bold'
                  }}
                >
                  ${position.unrealizedPNL.toFixed(2)}
                </TableCell>
                <TableCell 
                  align="right"
                  sx={{ 
                    color: position.dailyPNL >= 0 ? 'success.main' : 'error.main',
                    fontWeight: 'bold'
                  }}
                >
                  ${position.dailyPNL.toFixed(2)}
                </TableCell>
                <TableCell>
                  <Stack direction="row" spacing={1}>
                    {/* Show Buy button for SPY options (always) and MES (when short or no position) */}
                    {(position.contract.secType === 'OPT' || 
                      position.contract.symbol === 'MES') && (
                      <Button
                        variant="contained"
                        color="primary"
                        size="small"
                        onClick={() => handleBuyClick(position)}
                      >
                        {position.contract.symbol === 'MES' && position.position < 0 ? 'Cover' : 'Buy'}
                      </Button>
                    )}
                    
                    {/* Show Sell button for MES always, and for SPY only when long */}
                    {(position.contract.symbol === 'MES' || 
                      (position.contract.secType === 'OPT' && position.position > 0)) && (
                      <Button
                        variant="contained"
                        color="warning"
                        size="small"
                        onClick={() => handleSellClick(position)}
                      >
                        Sell
                      </Button>
                    )}
                    
                    {/* Show Close button for all positions */}
                    <Button
                      variant="contained"
                      color="error"
                      size="small"
                      onClick={() => closeMutation.mutate(position.contract.conId)}
                    >
                      Close
                    </Button>
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <BuyDialog
        open={buyDialogOpen}
        onClose={() => {
          setBuyDialogOpen(false);
          setSelectedPosition(null);
        }}
        onSubmit={handleBuySubmit}
        position={selectedPosition}
        isLoading={buyMutation.isLoading}
      />

      <SellDialog
        open={sellDialogOpen}
        onClose={() => {
          setSellDialogOpen(false);
          setSelectedPosition(null);
        }}
        onSubmit={handleSellSubmit}
        position={selectedPosition}
        isLoading={sellMutation.isLoading}
      />
    </Box>
  );
}

export default PositionsTable; 