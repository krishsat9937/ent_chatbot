import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Box, Card, Typography } from '@mui/material';

interface MessageProps {
  role: string;
  content: string;
}

const Message: React.FC<MessageProps> = ({ role, content }) => {
  const isBot = role === 'assistant';

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: isBot ? 'flex-start' : 'flex-end',
        mb: 1, // Adds spacing between messages
      }}
    >
      <Card
        sx={{
          maxWidth: '60%',
          p: 2,
          borderRadius: '16px',
          boxShadow: 3,
          backgroundColor: isBot ? 'blue.100' : 'grey.300',
          color: isBot ? 'grey.900' : 'common.black',
        }}
      >
        <Typography variant="subtitle1" component="strong">
          {isBot ? 'ENTBot' : 'You'}:
        </Typography>
        {/* Render markdown properly */}
        <ReactMarkdown>{content}</ReactMarkdown>
      </Card>
    </Box>
  );
};

export default Message;
