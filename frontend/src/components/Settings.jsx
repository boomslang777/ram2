import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Grid,
  Alert,
  Divider,
  Switch,
  FormControlLabel,
  FormGroup
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { TimePicker } from '@mui/x-date-pickers/TimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs from 'dayjs';
import QuickTradePanel from './QuickTradePanel';

function Settings() {
  const queryClient = useQueryClient();
  const [localSettings, setLocalSettings] = useState(null);
  const [strikes, setStrikes] = useState({
    ATM: null,
    calls: {
      'OTM-1': null,
      'OTM-2': null,
      'OTM-3': null,
    },
    puts: {
      'OTM-1': null,
      'OTM-2': null,
      'OTM-3': null,
    }
  });

  const { data: settings } = useQuery('settings', api.getSettings, {
    onSuccess: (data) => {
      if (!localSettings) {
        setLocalSettings(data);
      }
    }
  });

  useQuery('spy-price', api.getSpyPrice, {
    refetchInterval: 5000,
    onSuccess: (data) => {
      const price = data?.price || 0;
      const baseStrike = Math.round(price);
      
      setStrikes({
        ATM: baseStrike,
        calls: {
          'OTM-1': baseStrike + 1,
          'OTM-2': baseStrike + 2,
          'OTM-3': baseStrike + 3,
        },
        puts: {
          'OTM-1': baseStrike - 1,
          'OTM-2': baseStrike - 2,
          'OTM-3': baseStrike - 3,
        }
      });
    }
  });

  const currentSpyPrice = queryClient.getQueryData('spy-price')?.price;

  const updateSettingsMutation = useMutation(
    (newSettings) => api.updateSettings(newSettings),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('settings');
      }
    }
  );

  const handleSettingChange = (field) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    const newSettings = { ...localSettings, [field]: value };
    setLocalSettings(newSettings);
    updateSettingsMutation.mutate(newSettings);
  };

  const handleTimeChange = (newTime) => {
    const timeStr = newTime.format('HH:mm');
    const newSettings = { ...localSettings, auto_square_off_time: timeStr };
    setLocalSettings(newSettings);
    updateSettingsMutation.mutate(newSettings);
  };

  if (!localSettings) return null;

  return (
    <Box sx={{ mt: 4 }}>
      <QuickTradePanel />
      
      <Typography variant="h5" gutterBottom>
        Trading Settings
      </Typography>
      
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Position Size
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <TextField
                    fullWidth
                    type="number"
                    label="SPY Quantity"
                    value={localSettings.spy_quantity}
                    onChange={handleSettingChange('spy_quantity')}
                    InputProps={{ inputProps: { min: 1 } }}
                  />
                </Grid>
                <Grid item xs={6}>
                  <TextField
                    fullWidth
                    type="number"
                    label="MES Quantity"
                    value={localSettings.mes_quantity}
                    onChange={handleSettingChange('mes_quantity')}
                    InputProps={{ inputProps: { min: 1 } }}
                  />
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Auto Square Off Settings
              </Typography>
              <FormGroup>
                <FormControlLabel
                  control={
                    <Switch
                      checked={localSettings.auto_square_off_enabled}
                      onChange={handleSettingChange('auto_square_off_enabled')}
                    />
                  }
                  label="Enable Auto Square Off"
                />
                {localSettings.auto_square_off_enabled && (
                  <Box sx={{ mt: 2 }}>
                    <LocalizationProvider dateAdapter={AdapterDayjs}>
                      <TimePicker
                        label="Square Off Time (EST)"
                        value={dayjs(`2023-01-01T${localSettings.auto_square_off_time}`)}
                        onChange={handleTimeChange}
                        format="HH:mm"
                      />
                    </LocalizationProvider>
                  </Box>
                )}
              </FormGroup>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                SPY Options Settings
              </Typography>
              
              <Box sx={{ mb: 2 }}>
                <Typography color="primary" variant="h6">
                  Current SPY Price: ${currentSpyPrice?.toFixed(2) || 'Loading...'}
                </Typography>
              </Box>

              <Grid container spacing={2}>
                <Grid item xs={12} md={4}>
                  <FormControl fullWidth>
                    <InputLabel>Call Strike Selection</InputLabel>
                    <Select
                      value={localSettings.call_strike_selection}
                      onChange={handleSettingChange('call_strike_selection')}
                      label="Call Strike Selection"
                    >
                      <MenuItem value="ATM">ATM (${strikes.ATM})</MenuItem>
                      <MenuItem value="OTM-1">OTM+1 (${strikes.calls['OTM-1']})</MenuItem>
                      <MenuItem value="OTM-2">OTM+2 (${strikes.calls['OTM-2']})</MenuItem>
                      <MenuItem value="OTM-3">OTM+3 (${strikes.calls['OTM-3']})</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={12} md={4}>
                  <FormControl fullWidth>
                    <InputLabel>Put Strike Selection</InputLabel>
                    <Select
                      value={localSettings.put_strike_selection}
                      onChange={handleSettingChange('put_strike_selection')}
                      label="Put Strike Selection"
                    >
                      <MenuItem value="ATM">ATM (${strikes.ATM})</MenuItem>
                      <MenuItem value="OTM-1">OTM-1 (${strikes.puts['OTM-1']})</MenuItem>
                      <MenuItem value="OTM-2">OTM-2 (${strikes.puts['OTM-2']})</MenuItem>
                      <MenuItem value="OTM-3">OTM-3 (${strikes.puts['OTM-3']})</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={12} md={4}>
                  <FormControl fullWidth>
                    <InputLabel>Expiration</InputLabel>
                    <Select
                      value={localSettings.dte}
                      onChange={handleSettingChange('dte')}
                      label="Expiration"
                    >
                      <MenuItem value={0}>0 DTE (Today)</MenuItem>
                      <MenuItem value={1}>1 DTE (Tomorrow)</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

export default Settings;