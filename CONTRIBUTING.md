# Contributing to MCP Gateway

Thank you for your interest in contributing to the MCP Gateway! This document provides guidelines and information for contributors.

## 🎯 Project Vision

The MCP Gateway aims to be the leading open-source gateway for Model Context Protocol (MCP) interactions, providing enterprise-grade security, scalability, and developer experience.

## 🤝 How to Contribute

### Ways to Contribute

- **Code Contributions**: Bug fixes, new features, performance improvements
- **Documentation**: Improve docs, add examples, write tutorials
- **Testing**: Add test cases, improve test coverage, test different scenarios
- **Issue Reporting**: Report bugs, suggest features, improve error messages
- **Community Support**: Help others in discussions, answer questions
- **Design & UX**: Improve dashboard UI/UX, create diagrams, enhance user experience

### Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/bridge-mcp.git
   cd bridge-mcp
   ```
3. **Set up the development environment**:
   ```bash
   # Install uv if you haven't already
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Install dependencies
   uv sync --extra dev
   
   # Set up pre-commit hooks
   uv run pre-commit install
   ```

4. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 🔧 Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Git
- Docker (optional, for testing)

### Local Development

```bash
# Install all dependencies including dev tools
uv sync --extra dev

# Run the application
uv run python -m mcp_gateway.main

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=mcp_gateway --cov-report=html

# Code formatting and linting
uv run black src tests
uv run isort src tests
uv run flake8 src tests
uv run mypy src

# Run all quality checks
uv run pre-commit run --all-files
```

### Dashboard Development

```bash
cd dashboard
npm install
npm run dev  # Starts development server on http://localhost:5173
```

## 📝 Contribution Guidelines

### Code Standards

- **Python Style**: Follow PEP 8, use Black for formatting
- **Type Hints**: Use type hints for all public functions and methods
- **Documentation**: Document all public APIs with docstrings
- **Testing**: Write tests for new features and bug fixes
- **Async/Await**: Use async/await patterns for I/O operations

### Commit Messages

Use conventional commits format:

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(auth): add OAuth2 OBO token flow
fix(proxy): handle connection timeout gracefully
docs(api): update endpoint documentation
test(session): add MCP session management tests
```

### Pull Request Process

1. **Ensure your code follows the style guidelines**
2. **Add or update tests** for your changes
3. **Update documentation** if needed
4. **Ensure all tests pass** locally
5. **Create a pull request** with:
   - Clear title and description
   - Reference any related issues
   - Include screenshots for UI changes
   - List any breaking changes

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] Added new tests for changes
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

## 🏗️ Current Development Priorities

### Phase 2: MCP Protocol Compliance (Current Focus)
**Branch**: `mcp-spec-compliance`

**High Priority Issues:**
- MCP Client SDK integration
- Session management implementation  
- Streamable HTTP support
- Initialize handshake flow
- Circuit breaker integration

**Good First Issues:**
- Documentation improvements
- Test coverage enhancement
- Dashboard UI refinements
- Error message improvements
- Configuration validation

### Areas Needing Help

1. **MCP Protocol Implementation** - Help with SDK integration and compliance testing
2. **Security Enhancements** - Security audits, penetration testing, vulnerability fixes
3. **Performance Optimization** - Load testing, performance profiling, optimization
4. **Documentation** - API docs, tutorials, deployment guides, examples
5. **Testing** - Unit tests, integration tests, end-to-end testing
6. **Dashboard Features** - React components, data visualization, user experience

## 🐛 Reporting Issues

### Bug Reports

When reporting bugs, please include:

- **Environment**: OS, Python version, package versions
- **Steps to reproduce** the issue
- **Expected behavior** vs actual behavior
- **Error messages** and stack traces
- **Configuration** (sanitized, no secrets)

### Feature Requests

For feature requests, please provide:

- **Use case**: Why is this feature needed?
- **Proposed solution**: How should it work?
- **Alternatives considered**: Other approaches you've thought about
- **Additional context**: Any other relevant information

## 🧪 Testing Guidelines

### Test Categories

- **Unit Tests**: Test individual functions and methods
- **Integration Tests**: Test component interactions
- **Contract Tests**: Test MCP protocol compliance
- **Performance Tests**: Test under load conditions

### Writing Tests

```python
# Example test structure
import pytest
from mcp_gateway.core.session_manager import MCPSessionManager

class TestMCPSessionManager:
    def setup_method(self):
        self.session_manager = MCPSessionManager()
    
    async def test_create_session(self):
        # Test session creation
        session = await self.session_manager.get_or_create_session(
            client_id="test_client",
            server_url="http://localhost:3000"
        )
        assert session is not None
        assert session.client_id == "test_client"
    
    async def test_session_cleanup(self):
        # Test session cleanup
        # ... test implementation
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_session_manager.py -v

# Run with coverage
uv run pytest --cov=mcp_gateway --cov-report=term-missing

# Run only unit tests
uv run pytest tests/unit/ -v

# Run only integration tests  
uv run pytest tests/integration/ -v
```

## 📚 Documentation

### Documentation Types

- **API Documentation**: Automatic from docstrings
- **User Guides**: Step-by-step tutorials
- **Developer Guides**: Technical implementation details
- **Examples**: Code samples and use cases

### Writing Documentation

- Use clear, concise language
- Include code examples
- Add diagrams for complex concepts
- Keep documentation up-to-date with code changes

## 🌟 Recognition

### Contributor Levels

**Contributors**: Anyone who submits a merged PR
**Regular Contributors**: 3+ merged PRs and ongoing engagement
**Core Contributors**: Significant ongoing contributions and project involvement
**Maintainers**: Project leadership and decision-making authority

### Ways We Recognize Contributors

- Contributor section in README
- Release notes mentions
- Social media recognition
- Conference speaking opportunities (for significant contributors)

## 📧 Contact & Communication

### Getting Help

1. **GitHub Discussions**: Best for questions, ideas, and community interaction
   - [Start a discussion](https://github.com/codingjam/bridge-mcp/discussions)

2. **GitHub Issues**: For bug reports and feature requests
   - [Open an issue](https://github.com/codingjam/bridge-mcp/issues)

3. **Pull Request Reviews**: For code-specific discussions
   - Comment on specific lines in PRs

### Project Communication

- **Public Discussions**: Use GitHub Discussions for transparency
- **Code Reviews**: Respectful, constructive feedback in PRs
- **Issue Tracking**: Clear, detailed issue descriptions

### Becoming a Core Contributor

Interested in deeper involvement? Here's how:

1. **Consistent Contributions**: Regular PRs and community engagement
2. **Quality Focus**: High-quality code and thorough testing
3. **Communication**: Active participation in discussions and reviews
4. **Initiative**: Propose and drive significant improvements
5. **Mentorship**: Help other contributors and answer questions

**Express Interest**: If you're interested in becoming a core contributor, open a GitHub Discussion with:
- Your background and relevant experience
- Areas where you'd like to contribute
- Time commitment you can make
- Vision for the project

### Maintainer Contact

For sensitive issues, project direction discussions, or core contributor applications:
- **GitHub**: [@parth](https://github.com/parth) (or open a private discussion)
- **Project Discussions**: For most project-related communication
- **Issues**: For specific bugs or feature requests

*We prefer public communication via GitHub for transparency and community building.*

## 🚀 Release Process

### Version Management

- **Semantic Versioning**: MAJOR.MINOR.PATCH
- **Release Branches**: `release/vX.Y.Z`
- **Development**: Feature branches from `develop`
- **Production**: Releases merged to `main`

### Release Schedule

- **Major Releases**: Quarterly (breaking changes, major features)
- **Minor Releases**: Monthly (new features, improvements)
- **Patch Releases**: As needed (bug fixes, security updates)

## 📄 Code of Conduct

### Our Standards

- **Respectful Communication**: Be kind and professional
- **Inclusive Environment**: Welcome all backgrounds and experience levels
- **Constructive Feedback**: Focus on improving the code and project
- **Collaborative Spirit**: Work together towards common goals

### Unacceptable Behavior

- Harassment, discrimination, or hate speech
- Personal attacks or trolling
- Publishing private information
- Other conduct reasonably considered inappropriate

### Enforcement

Report any issues to the maintainers via:
- Private GitHub discussion
- Email (if provided in repository settings)

## 🙏 Thank You

Every contribution makes this project better. Whether you're fixing a typo, adding a feature, or helping other users, your effort is valued and appreciated!

## 📖 Additional Resources

- [MCP Protocol Specification](https://github.com/modelcontextprotocol/specification)
- [Project Requirements Document](docs/MCP_Gateway_PRD.md)
- [Implementation Plan](docs/MCP_Compliance_Implementation_Plan.md)
- [API Documentation](docs/) (when available)

---

*This contributing guide is a living document. Suggestions for improvements are welcome!*
