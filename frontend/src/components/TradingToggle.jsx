import { Switch, FormControlLabel, Box, Typography } from '@mui/material';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { api } from '../services/api';

function TradingToggle() {
  const queryClient = useQueryClient();
  
  const { data: settings } = useQuery('settings', api.getSettings);

  const mutation = useMutation(
    (enabled) => api.updateSettings({ ...settings, trading_enabled: enabled }),
    {
      onSuccess: () => queryClient.invalidateQueries('settings')
    }
  );

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
      <FormControlLabel
        control={
          <Switch
            checked={settings?.trading_enabled || false}
            onChange={(e) => mutation.mutate(e.target.checked)}
            color="success"
          />
        }
        label="Trading Enabled"
      />
      <Typography
        variant="h6"
        color={settings?.trading_enabled ? 'success.main' : 'error.main'}
        sx={{ fontWeight: 'bold' }}
      >
        Trading is {settings?.trading_enabled ? 'ACTIVE' : 'DISABLED'}
      </Typography>
    </Box>
  );
}

export default TradingToggle; 