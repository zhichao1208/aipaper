# AI Paper+ 🎙️

AI Paper+ is an innovative project that automatically transforms academic papers into engaging podcast episodes. It uses AI to analyze research papers, generate comprehensive summaries, and convert them into natural-sounding audio content.

## Features

- 📝 Paper Analysis: Support for direct paper links, titles, and abstracts
- 🤖 AI-Powered Summary: Intelligent paper summarization using advanced language models
- 🎙️ Audio Generation: High-quality text-to-speech conversion
- 🎧 Podcast Publishing: Automatic upload to podcast platforms
- 📊 Real-time Status: Live progress tracking and status updates
- 🌐 Web Interface: User-friendly Streamlit interface

### API Services Setup

1. **NotebookLM API**: Used for paper processing and content generation
   - Sign up at [AutoContent API](https://api.autocontentapi.com)
   - Get your API key from the dashboard

2. **OpenAI API**: Used for content enhancement and summarization
   - Sign up at [OpenAI](https://openai.com)
   - Create an API key in your account settings

3. **Podbean**: For podcast hosting and distribution
   - Create an account at [Podbean](https://www.podbean.com)
   - Set up API credentials in your developer settings

4. **Cloudinary**: For audio file storage
   - Sign up at [Cloudinary](https://cloudinary.com)
   - Get your cloud name and API credentials

5. **Jina AI**: For PDF processing (optional)
   - Register at [Jina AI](https://jina.ai)
   - Obtain your access token

### Running the Application

1. Start the webhook server:
```bash
python webhook_server.py
```

2. Launch the main application:
```bash
streamlit run aipaper_app.py
```

## Future Enhancements

- [ ] Support for more paper sources
- [ ] Enhanced audio quality options
- [ ] Multiple language support
- [ ] Batch processing capability
- [ ] Weekly paper review automation
- [ ] Search and selection from paper databases
