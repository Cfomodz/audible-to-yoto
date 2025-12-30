# Contributing to Audible to Yoto Converter

Thank you for considering contributing! Here's how you can help.

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in Issues
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - System information (OS, Python version, etc.)
   - Error messages and logs

### Suggesting Features

1. Check if the feature has been suggested
2. Create a new issue describing:
   - The problem it solves
   - Proposed solution
   - Alternative solutions considered
   - Any additional context

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test thoroughly
5. Commit with clear messages
6. Push to your fork
7. Open a Pull Request

### Code Style

- Follow PEP 8 for Python code
- Use meaningful variable names
- Add comments for complex logic
- Update documentation as needed

### Testing

- Test your changes with real audiobooks
- Verify on different operating systems if possible
- Check that existing functionality still works

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/audible-to-yoto.git
cd audible-to-yoto

# Setup development environment
./setup.sh
source venv/bin/activate

# Install development dependencies
pip install -r requirements.txt

# Make your changes
# ...

# Test
./convert_audiobooks.sh
```

## Areas for Contribution

### High Priority
- Automated icon upload to Yoto API
- Batch JSON editing with icon IDs
- Web interface for easier use
- Docker container
- Windows support improvements

### Medium Priority
- Additional icon styles
- Cover image quality improvements
- Progress bar enhancements
- Logging improvements

### Documentation
- Video tutorials
- More examples
- Troubleshooting guides
- Translation to other languages

## Questions?

Feel free to open an issue for questions or join discussions.

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what's best for the project
- Show empathy towards others

Thank you for contributing! 🎉
