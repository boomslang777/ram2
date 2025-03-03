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
  CircularProgress
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { api } from '../services/api';

function OrdersTable() {
  const queryClient = useQueryClient();

  const { data: orders, isLoading } = useQuery('orders', api.getOrders, {
    refetchInterval: 1000
  });

  const cancelMutation = useMutation(
    (orderId) => api.cancelOrder({ order_id: Number(orderId) }),
    {
      onSuccess: () => queryClient.invalidateQueries('orders')
    }
  );

  const canCancelOrder = (status) => {
    return !['Filled', 'Cancelled', 'Completed', 'Inactive'].includes(status);
  };

  if (isLoading) {
    return <CircularProgress />;
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Orders
      </Typography>
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Order ID</TableCell>
              <TableCell>Symbol</TableCell>
              <TableCell>Action</TableCell>
              <TableCell align="right">Quantity</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {orders?.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  No orders
                </TableCell>
              </TableRow>
            ) : (
              orders?.map((order) => (
                <TableRow key={order.orderId}>
                  <TableCell>{order.orderId}</TableCell>
                  <TableCell>{order.contract.localSymbol}</TableCell>
                  <TableCell>{order.action}</TableCell>
                  <TableCell align="right">{order.totalQuantity}</TableCell>
                  <TableCell>{order.orderType}</TableCell>
                  <TableCell>{order.status}</TableCell>
                  <TableCell>
                    {canCancelOrder(order.status) && (
                      <Button
                        variant="contained"
                        color="error"
                        size="small"
                        onClick={() => cancelMutation.mutate(order.orderId)}
                      >
                        Cancel
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

export default OrdersTable; 