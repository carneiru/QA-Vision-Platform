# ADR-006: Select Python for AI/ML Services

- Status: Accepted
- Date: 2024-02-19
- Authors: Architecture Team
- Decision Owner: Chief Architect
- Supersedes: None
- Superseded By: None

---

# Context

## Business Problem
Developing AI/ML capabilities for the QEOS platform’s Quality Intelligence Platform (QIP) domain required a language with strong support for data science, machine learning, and artificial intelligence workloads. The AI/ML services need rapid prototyping, extensive scientific libraries, and robust community backing for research and production.

## Technical Problem
AI/ML workloads demand heavy numerical computation, matrix manipulation, statistical analysis, and complex algorithm implementation. Many general‑purpose languages lack the specialized libraries and optimized numerical computing needed for efficient AI/ML development. Moreover, the data science ecosystem has converged on specific languages, establishing de facto standards for interoperability and collaboration.

## Architectural Drivers
- Access to extensive machine learning and scientific computing libraries  
- Excellent data manipulation and analysis capabilities  
- Support for rapid prototyping and iterative development  
- Strong community and ecosystem for AI/ML research and development  
- Interoperability with data science tools and notebooks (Jupyter, etc.)  
- Ability to leverage hardware acceleration (GPUs, TPUs) for training/inference  
- Support for production deployment of ML models at scale  
- Integration with data pipelines and workflow orchestration systems  

## Constraints
- Integration with the existing technology stack and microservices architecture  
- Deployability in our containerized environment (Docker/Kubernetes)  
- Interoperability with services written in other languages (Go, Node.js)  
- Compliance with enterprise security standards  
- Team familiarity or willingness to adopt the language  
- Performance requirements for serving ML models in production  
- Licensing considerations for commercial use of libraries  

## Assumptions
- Organization is willing to invest in Python expertise for AI/ML teams  
- Existing CI/CD pipelines can accommodate Python‑based services  
- Sufficient learning resources and training are available for data science teams  
- The Python data science ecosystem provides the necessary libraries for our AI/ML needs  
- Hardware acceleration support (CUDA, etc.) is available in our deployment environments  
- Long‑term viability of Python for AI/ML is assured given its dominance in the field  

## Quality Attributes Involved
- Developer productivity  
- Ecosystem richness  
- Computational performance (with appropriate libraries)  
- Deployability and scalability  
- Maintainability  
- Integration capability  

---

# Decision
Select Python 3.11+ as the primary language for developing AI/ML services in the QEOS platform’s Quality Intelligence Platform (QIP) domain due to its unparalleled ecosystem for data science, machine learning, and artificial intelligence, combined with excellent productivity for rapid experimentation and strong production deployment capabilities.

## Scope
This decision applies to all AI/ML services within the Quality Intelligence Platform (QIP) domain, including but not limited to: model training services, inference services, feature engineering services, data preprocessing services, experiment tracking services, and AI‑powered analytics APIs.

## Affected Domains
Primarily affects the Quality Intelligence Platform (QIP) domain, but AI/ML capabilities may be consumed by other domains: Platform, Execution, Automation, Collaboration, Administration, Marketplace, and Integrations.

## Implementation Boundaries
- Python 3.11+ as minimum version for all AI/ML services  
- Use of virtual environments or containers for dependency isolation  
- Standard Python packaging (setup.py, pyproject.toml, or Poetry)  
- Jupyter notebooks for experimentation and documentation where appropriate  
- Type hints for improved code quality and IDE support (using mypy or similar)  
- Virtual environments for dependency management  
- Containerization using Docker with multi‑stage builds for production images  
- GPU‑aware base images (nvidia/cuda) for ML workloads requiring acceleration  
- MLflow or similar for model tracking, versioning, and serving  
- Integration with experiment tracking systems (Weights & Biases, MLflow, etc.)  
- API exposure through FastAPI, Flask, or similar Python web frameworks  
- Asynchronous processing using asyncio or Celery for background tasks  
- Data validation using Pydantic or similar libraries  
- Monitoring and logging integration with existing observability stack  

---

# Alternatives Considered

## R
**Pros**
- Excellent statistical analysis and visualization capabilities  
- Comprehensive package ecosystem (CRAN) for statistics and data science  
- Strong in academia and research communities  
- Excellent data visualization libraries (ggplot2, plotly)  
- Designed specifically for statistical computing and graphics  

**Cons**
- Steeper learning curve for programmers from other backgrounds  
- Less suitable for general‑purpose software development  
- Weaker support for building large‑scale applications  
- Less ideal for production deployment of ML models as services  
- Smaller community for web development and API creation  
- Memory management can be less efficient than Python alternatives  
- Fewer options for microservices and cloud‑native deployment patterns  

**Decision**: Not selected  
**Rejection Reason**: While R excels at statistical analysis, its limitations in general‑purpose programming, web development, and production deployment make it less suitable for building comprehensive AI/ML services that must integrate into a larger microservices architecture.

## Julia
**Pros**
- High‑performance just‑in‑time (JIT) compilation  
- Excellent for numerical and scientific computing  
- Syntax familiar to users of MATLAB, Python, and R  
- Growing ecosystem for machine learning and data science  
- Built‑in support for parallel and distributed computing  
- Increasing adoption in scientific computing communities  

**Cons**
- Smaller ecosystem compared to Python for ML/AI  
- Less mature tooling for production deployment and monitoring  
- Smaller community and fewer learning resources  
- Longer startup times due to JIT compilation  
- Fewer options for web frameworks and API development  
- Less established practices for MLOps and model deployment  
- Limited integration with big data tools compared to Python  

**Decision**: Not selected  
**Rejection Reason**: While Julia offers impressive performance, its smaller ecosystem and less mature tooling for production ML systems make it less suitable for our needs compared to Python, which has become the lingua franca of AI/ML development.

## Java/Spring Boot
**Pros**
- Mature enterprise ecosystem with strong tooling  
- Excellent performance with JVM optimizations  
- Strong typing and compile‑time safety  
- Good performance for serving ML models  
- Established practices for enterprise application development  
- Strong integration with big data ecosystems (Hadoop, Spark)  

**Cons**
- Verbose syntax and boilerplate code  
- Longer development cycles compared to Python  
- Heavier weight containers and higher resource usage  
- Less agile for rapid experimentation and prototyping  
- Steeper learning curve for data science teams  
- Fewer ML‑specific libraries compared to Python ecosystem  
- Less interactive and exploratory development experience  
- Longer startup times affecting scaling characteristics  

**Decision**: Not selected  
**Rejection Reason**: Java’s strengths in enterprise development are outweighed by its verbosity and slower development cycle for AI/ML work, where rapid experimentation and access to cutting‑edge research implementations are crucial.

## C++/CUDA
**Pros**
- Highest possible performance for computation‑intensive tasks  
- Direct access to GPU capabilities through CUDA  
- Fine‑grained control over memory and computation  
- Extensive use in high‑performance computing and game industries  
- Mature ecosystem for low‑level systems programming  

**Cons**
- Significantly higher complexity and development time  
- Manual memory management increases risk of bugs  
- Steep learning curve for effective use  
- Lack of built‑in garbage collection  
- Poor suitability for rapid prototyping and experimentation  
- Limited ecosystem for data science and ML compared to Python  
- Difficult to maintain and extend large codebases  
- Not ideal for web services and API development  
- Longer compilation cycles affecting developer productivity  

**Decision**: Not selected  
**Rejection Reason**: While C++/CUDA offers unmatched performance, its complexity and lack of productive ecosystem for AI/ML development make it impractical for the majority of our AI/ML work, where rapid iteration and access to latest research are more valuable than absolute peak performance for most workloads.

## JavaScript/TypeScript (Node.js)
**Pros**
- Single language across frontend and backend  
- Good performance for I/O‑bound operations  
- Large npm ecosystem  
- Growing machine learning libraries (TensorFlow.js, etc.)  
- Excellent for real‑time applications and websockets  

**Cons**
- Single‑threaded nature limits CPU‑bound performance  
- Less mature ecosystem for serious ML/data science work  
- Memory leaks and performance issues can be challenging to diagnose  
- Not the primary language of choice in the data science community  
- Limited hardware acceleration support compared to Python/C++  
- Fewer options for scientific computing and numerical analysis  
- Less suitable for batch processing and model training workloads  

**Decision**: Not selected  
**Rejection Reason**: JavaScript/Node.js, while excellent for certain services, lacks the depth and breadth of the Python data science ecosystem essential for AI/ML workloads, particularly for model training, experimentation, and research.

---

# Consequences

## Positive
- Access to the most extensive and mature ecosystem for data science and machine learning  
- Excellent libraries for numerical computation (NumPy), data manipulation (pandas), and scientific computing (SciPy)  
- Leading machine learning frameworks (TensorFlow, PyTorch, scikit‑learn) with first‑class Python support  
- Rich visualization ecosystem (matplotlib, seaborn, plotly, bokeh)  
- Strong support for experiment tracking and MLOps (MLflow, Weights & Biases, etc.)  
- Excellent readability and ease of learning for data scientists  
- Rapid prototyping capabilities accelerate innovation cycles  
- Strong community and abundant learning resources  
- Good integration with Jupyter notebooks for exploratory analysis  
- Strong support for asynchronous programming (asyncio, trio)  
- Excellent API development frameworks (FastAPI, Flask, Django REST Framework)  
- Strong testing and debugging tools (pytest, unittest, pdb)  
- Widely adopted in industry, easing hiring and collaboration  
- Comprehensive documentation and third‑party learning materials  
- Regular releases with performance improvements and new features  
- Strong support for type hints and static analysis (mypy, pyright)  

## Negative
- Global Interpreter Lock (GIL) limits true parallelism in CPython  
- Interpreted nature can lead to higher resource usage than compiled languages  
- Dynamic typing can lead to runtime errors caught at compile time in statically typed languages  
- Package dependency management can be complex (mitigated with proper tooling)  
- Performance limitations for certain computational workloads  
- Memory consumption can exceed more lightweight alternatives  
- Need for careful consideration of asynchronous vs synchronous patterns  
- Potential version conflicts between scientific libraries  
- Security considerations for executing user‑provided code (in notebooks, etc.)  
- Overwhelming number of choices can lead to decision fatigue  

---

# Implementation

## Affected Services
AI/ML services in QIP domain: Model Training Service, Inference Service, Feature Store Service, Data Preprocessing Service, Experiment Tracking Service, Model Registry Service, Anomaly Detection Service, Prediction Service, NLP Processing Service, Computer Vision Service, Recommendation Service, Forecasting Service

## Affected Domains
Primarily Quality Intelligence Platform (QIP) domain, with consumption by: Platform, Execution, Automation, Collaboration, Administration, Marketplace, and Integrations domains

## Deployment Implications
- Docker images based on python:3.11‑slim or similar base images  
- Multi‑stage builds to reduce final image size  
- Non‑root user execution for security  
- GPU‑enabled base images (nvidia/cuda:XX.X‑runtime‑ubuntu22.04) for ML workloads  
- Resource requests and limits for CPU, memory, and GPU where applicable  
- Health checks (liveness/readiness) for Kubernetes orchestration  
- Horizontal Pod Autoscaler based on custom metrics (queue depth, latency)  
- Pod Disruption Budgets for high availability of critical services  
- ConfigMaps and Secrets for configuration and sensitive data  
- Init containers for database migrations or model preloading  
- Sidecar pattern for log aggregation, metrics export, or security proxies  
- Service definitions for internal service discovery  
- Ingress controllers for external API access where needed  
- Istio/Linkerd service mesh integration for advanced traffic management  

## Operational Considerations
- Structured logging (JSON) to stdout/stderr for aggregation  
- Prometheus metrics endpoint for monitoring  
- Distributed tracing context propagation (OpenTelemetry/Jaeger)  
- Health check endpoints for liveness and readiness  
- Model versioning and metadata tracking  
- Input validation and sanitization for API security  
- Rate limiting and abuse protection for public APIs  
- Logging of predictions and feedback for continuous improvement  
- A/B testing framework for model comparisons  
- Canary deployment strategies for model updates  
- Data drift detection and monitoring  
- Concept drift detection for production models  
- Explainability and interpretability tools for model debugging  
- Model card generation for transparency and compliance  
- Regular security scanning of dependencies (safety, bandit)  
- CPU/GPU utilization monitoring and optimization  
- Memory leak detection and prevention  
- Container image vulnerability scanning (Trivy, Clair, etc.)  
- Dependency update automation with security patching  
- Log retention and archiving policies  
- Audit trails for model usage and predictions  

## Migration Considerations
- Phase 1: Establish Python development standards and environment  
- Phase 2: Create base Docker images and templates for ML services  
- Phase 3: Develop shared libraries for data access, model loading, and common utilities  
- Phase 4: Implement experiment tracking and model registry services  
- Phase 5: Migrate existing AI/ML prototypes to production services  
- Phase 6: Establish CI/CD pipelines for Python ML services (testing, building, deploying)  
- Phase 7: Implement monitoring, logging, and tracing instrumentation  
- Phase 8: Create API contracts and documentation standards (OpenAPI/Swagger)  
- Phase 9: Develop performance optimization strategies (caching, batching, async)  
- Phase 10: Implement model validation and testing frameworks  
- Phase 11: Establish MLOps practices for continuous training and deployment  
- Phase 12: Create knowledge sharing and training programs for teams  
- Phase 13: Plan for ongoing framework and library updates  
- Phase 14: Implement advanced features (online learning, ensemble methods, etc.)  

---

# Risks

| Risk | Mitigation |
|------|------------|
| Dependency conflicts and version incompatibilities | Use virtual environments, poetry or pip‑tools for lockfiles; perform regular dependency audits |
| Performance bottlenecks in CPU‑intensive workloads | Use NumPy/Pandas for vectorization; consider Cython or Numba for critical paths; profile and optimize |
| Memory leaks in long‑running services | Implement memory profiling; use object pools where appropriate; enforce resource limits |
| Security vulnerabilities in Python packages | Use safety/bandit for scanning; maintain approved package lists; perform regular updates |
| Model drift and degradation in production | Implement monitoring for data/concept drift; establish retraining triggers; A/B testing framework |
| Difficulty reproducing results due to environment differences | Use containerization, lock files, and environment documentation for reproducibility |
| Challenges with GPU driver compatibility and installation | Use standardized base images; document GPU requirements; test in staging environments |
| Team skill gaps in modern Python practices | Provide training in type hints, asyncio, and modern Python idioms; enforce code reviews |
| Over‑reliance on Jupyter notebooks leading to technical debt | Establish clear boundaries between experimentation and production code; use notebooks appropriately |
| Licensing issues with certain ML frameworks or models | Maintain approved license list; conduct legal review of dependencies; consider LGPL/GPL implications |
| Scalability challenges for model serving | Implement model batching; use Triton Inference Server; consider model quantization/distillation |

---

# Related Decisions
- ADR-001: Adopt Domain‑Driven Design  
- ADR-002: Adopt Event‑Driven Architecture  
- ADR-003: Select Kubernetes as Container Orchestrator  
- ADR-004: Select Apache Kafka as Event Backbone  
- ADR-005: Select Go for Core Infrastructure Services  
- ADR-007: Select React/TypeScript for Frontend Applications  
- ADR-008: Select PostgreSQL as Primary Relational Database  
- ADR-009: Select Neo4j for Knowledge Graph Storage  
- ADR-010: Select Qdrant for Vector Database  
- ADR-017: Bounded Context Map and Context Mapping  
- ADR-018: Event Sourcing and CQRS Patterns  
- ADR-019: Dead Letter Queue Handling  
- ADR-020: Service Mesh Adoption  

---

# References
- Python Documentation  
- NumPy: Array processing for numbers, strings, records, and objects  
- pandas: Python Data Analysis Library  
- scikit‑learn: Machine Learning in Python  
- TensorFlow: An End‑to‑End Open Source Machine Learning Platform  
- PyTorch: Tensors and Dynamic Neural Networks  
- Keras: Deep Learning API for TensorFlow  
- Flask: A microframework for Python  
- FastAPI: Modern, fast (high‑performance), web framework for building APIs with Python  
- Django: The Web framework for perfectionists with deadlines  
- SQLAlchemy: The Python SQL Toolkit and Object Relational Mapper  
- Alembic: A lightweight database migration tool for usage with SQLAlchemy  
- Pydantic: Data validation and settings management using Python type annotations  
- FastAPI Users: FastAPI Users – modern, safe, and lightweight user management  
- SQLModel: SQL databases in Python, designed for simplicity, compatibility, and robustness  
- Uvicorn: Lightning‑fast ASGI server, built on uvloop and httptools  
- Gunicorn: Python WSGI HTTP Server for UNIX  
- Celery: Distributed Task Queue  
- Redis: Redis Python Client  
- Loguru: Python logging made (stupidly) simple  
- structlog: Structured logging for Python  
- PyTest: Framework for writing tests  
- Hypothesis: Modern, property‑based testing for Python  
- Black: The uncompromising Python code formatter  
- isort: A Python utility/library to sort imports  
- Flake8: Your tool For Style Guide Enforcement  
- mypy: Optional static typing for Python  
- Pillow: Python Imaging Library (fork of PIL)  
- Requests: HTTP library for Python  
- aiohttp: Asynchronous HTTP client/server for asyncio and asyncio‑streams  
- Beautiful Soup: Library for pulling data out of HTML and XML files  
- lxml: Processing XML and HTML in the Python language  
- openpyxl: A python library to read/write Excel 2010 xlsx/xlsm/xltx/xltm files  
- PyPDF2: Pure‑python PDF library for splitting, merging, cropping, and transforming PDFs  
- tabula‑py: Extract table from PDF using Python  
- pandas‑profiling: Simple pandas DataFrame profiling report  
- streamlit: Streamlit — The fastest way to build data apps  
- Dash: A Python Framework for Building Reactive Web Applications  
- Panel: A powerful library for both exploratory and interactive applications  
- Voila: Jupyter notebooks without the code  
- NLTK: Natural Language Toolkit  
- spaCy: Industrial‑strength Natural Language Processing  
- transformers: State‑of‑the‑art Machine Learning for PyTorch and TensorFlow  
- sentence‑transformers: Sentence Embeddings  
- langchain: Building applications with LLMs through composability  
- Hugging Face Transformers: State‑of‑the‑art Machine Learning for PyTorch, TensorFlow, and JAX  
- MLflow: Open source platform for the machine learning lifecycle  
- Weights & Biases: Tools for machine learning  
- Evidently: Evidently – ML model monitoring and test generation  
- WhyLogs: WhyLabs’ open  
- Data Validation: Library for validating and manipulating tabular data  
- Great Expectations: Always know what to expect from your data  
- FEATUREtools: Automated feature engineering  
- tslearn: A machine‑learning toolkit dedicated to time‑series data  
- sktime: A Unified Toolbox for Time Series Learning  
- Prophet: Forecasting procedure  
- statsmodels: Statistical modeling and econometrics in Python  
- scikit‑survival: Survival analysis for scikit‑learn  
- lifelines: Survival analysis in Python  
- imbalanced‑learn: Under Sampling, Over Sampling, Combination Sampling, and Ensemble Sampling  
- category_encoders: Categorical encoding scikit‑learn compatible  
- sklearn‑pandas: A bridge between scikit‑learn and pandas  
- mlxtend: Extension and helper modules for Python machine learning libraries  
- pomegranate: Probabilistic modeling  
- annoy: Approximate Nearest Neighbors in C++/Python optimized for memory usage  
- faiss: A library for efficient similarity search and clustering of dense vectors  
- nmslib: Non‑Metric Space Library (NMSLIB) is an effective tool for doing approximate  
- hnswlib: Approximate nearest neighbor search in C++/Python optimized for memory usage  
- spotipy: Spotify Web API Python Edition  
- tweepy: Twitter API client  
- praw: Python Reddit API Wrapper  
- instaloader: Download pictures (or videos) from Instagram  
- facebook‑scraper: Facebook Page and Group Scraper  
- reddit‑wrapper: Reddit API Wrapper  
- yfinance: Yahoo! Financials Download  
- alpha_vantage: Alpha Vantage API  
- finnhub: Finnhub Python Client  
- quandl: Quandl Python API  
- beautifulsoup4: Building.py  
- selenium: Selenium Python bindings  
- webdriver‑manager: WebDriver manager for python  
- Playwright: Python library to automate Chromium, Firefox, and WebKit browsers  
- requests‑html: HTML Parsing for Humans!  
- newspaper3k: News, full‑text, and article meta data extraction in Python 3  
- advertools: Advertising (Google, Facebook, Twitter, Amazon, etc.) Analysis  
- apyori: Apriori algorithm  
- mlxtend.frequent_patterns: Frequent Pattern Mining  
- pyod: Python Outlier Detection  
- PyOD: Python Toolbox for Scalable Outlier Detection (Detection)  
- scipy: Scientific Library for Python  
- statsmodels: Statistical models and econometrics in Python  
- sympy: Python library for symbolic mathematics  
- NetworkX: Software for complex networks  
- igraph: Network analysis and visualization  
- torch: Tensors and Dynamic neural networks in Python with strong GPU acceleration  
- tensorflow: An end‑to‑end open source platform for machine learning  
- keras: Deep Learning API  
- lightgbm: Gradient boosting framework  
- xgboost: Extreme Gradient Boosting  
- catboost: Gradient Boosting on Decision Trees  
- shap: Shapley values  
- lime: Local Interpretable Model‑agnostic Explanations  
- eli5: Explain predictions and inspect machine learning models  
- yellowbrick: Visualizer for scikit‑learn  
- matplotlib: Plotting library for Python and numerical mathematics extension to NumPy  
- seaborn: Statistical data visualization  
- plotly: Python graphing library  
- bokeh: Interactive visualization library for modern web browsers  
- altair: Declarative statistical visualization library for Python  
- pydeck: Python interface to Deck.gl  
- folium: Leaflet.js for Python  
- deepnote: Data science notebooks for teams  
- streamlit: Streamlit — The fastest way to build data apps  
- voila: Jupyter notebooks without the code  
- panel: High level apps and dashboards  
- jupyterlab: JupyterLab computational environment  
- notebook: Jupyter Notebook  
- jupyter: Jupyter  
- ipywidgets: Interactive HTML widgets for Jupyter notebooks and IPython  
- dvc: Data Science Version Control  
- lakeFS: LakeFS – data version control built on Git  
- pudl: Public Utility Data Liberation  
- whylogs: WhyLogs – WhyLabs’ open  
- evidently: Evidently – ML model monitoring and test generation  
- molotov: Molotov – asynchronous load testing tool  
- locust: Locust – scalable user load testing tool written in Python  
- k6: k6 – a modern load testing tool  
- locust‑io: Locust – a pure Python load testing tool for testing websites  
- welder: Welder – a high‑performance static site generator for Python  
- sphinx: Sphinx – Python documentation generator  
- mkdocs: Markdown documentation  
- pdoc: pdoc3 – pretty quick and clean documentation generator  
- doxygen: Doxygen – Documentation generator  
- pydoc: pydoc – documentation tool  
- epydoc: epydoc – Python API documentation generation tool  
- yardoc: Yardoc – Documentation generator for Ruby  
- doxyrest: Doxyrest – C++ to Markdown documentation generator  
- swift‑doc: Swift‑Doc – Documentation generator for Swift  
- jazzy: Jazzy – Objective‑C / Swift documentation generator  
- apidoc: apidoc – RESTful web API Documentation Generator  
- swagger‑ui: Swagger UI  
- redoc: ReDoc – OpenAPI/Swagger‑generated API reference documentation  
- swagger: Swagger – openapi 2.0  
- openapi‑generator: OpenAPI Generator  
- swagger‑core: Swagger Core  
- rest‑assured: io.rest‑assured  
- postman: Postman  
- insomnia: Insomnia Core  
- graphql: GraphQL  
- apollo‑server: Apollo Server  
- graphql‑yoga: GraphQL Yoga  
- type‑graphql: TypeGraphQL  
- nestjs: NestJS Framework  
- loopback: LoopBack  
- sails: Sails.js  
- feathers: FeathersJS  
- hapi: @hapi/hapi  
- loopback‑datasource‑juggler: LoopBack DataSource Juggler  
- strongloop: StrongLoop Arc  
- mean: MEAN  
- meteor: Meteor  
- sails‑hook‑sockets: Sails Hook Sockets  
- feathers‑mongoose: Feathers Mongoose  
- loopback‑connector‑mongodb: LoopBack MongoDB Connector  
- mongoose: Mongoose  
- mongodb: MongoDB  
- mongosh: MongoDB Shell  
- mongoose‑legacy‑plugins: Mongoose Legacy Plugins  
- mongodb‑memory‑server: MongoDB Memory Server  
- mongodb‑stitch: MongoDB Stitch  
- mongodb‑stitch‑admin‑sdk: MongoDB Stitch Admin SDK  
- mongodb‑stitch‑android‑sdk: MongoDB Stitch Android SDK  
- mongodb‑stitch‑browser‑sdk: MongoDB Stitch Browser SDK  
- mongodb‑stitch‑react‑native‑sdk: MongoDB Stitch React Native SDK  
- mongodb‑stitch‑sdk: MongoDB: The Definitive Guide  
- Designing Data‑Intensive Applications — Martin Kleppmann  
- Pattern Recognition and Machine Learning — Christopher Bishop  
- Deep Learning — Ian Goodfellow, Yoshua Bengio, and Aaron Courville  
- Hands‑On Machine Learning with Scikit‑Learn, Keras, and TensorFlow — Aurélien Géron  
- Python Machine Learning — Sebastian Raschka and Vahid Mirjalili  
- Intro to Machine Learning with PyTorch and Lightning — Luis Serrano  
- Natural Language Processing with Python — Steven Bird, Ewan Klein, and Edward Loper  
- Speech and Language Processing — Daniel Jurafsky and James H. Martin  
- Computer Vision: Algorithms and Applications — Richard Szeliski  
- Deep Learning for Computer Vision — Adrian Rosebrock  
- Programming Collective Intelligence — Toby Segaran  
- Reinforcement Learning: An Introduction — Richard Sutton and Andrew Barto  
- Bayesian Methods for Hackers — Cam Davidson‑Pilon  
- Think Stats — Allen B. Downey  
- Fluids — Allen B. Downey  
- Think Complexity — Allen B. Downey  
- Bayesian Analysis with Python — Osvaldo Martin  
- Probabilistic Programming & Hackers — Cam Davidson‑Pilon  
- Machine Learning Yearning — Andrew Ng  
- Deep Learning with Python — François Chollet  
- Deep Learning for Coders with fastai and PyTorch — Jeremy Howard and Sylvain Gugger  
- First Principles — Thomas C. Taylor  
- The Art of Statistics — David Spiegelhalter  
- Statistics — Robert S. Witte and John S. Witte  
- Naked Statistics — Charles Wheelan  
- The Art of R Programming — Norman Matloff  
- R for Data Science — Hadley Wickham and Garrett Grolemund  
- Hands‑On Programming with R — Garrett Grolemund  
- R Packages — Hadley Wickham  
- ggplot2: Elegant Graphics for Data Analysis — Hadley Wickham  
- Advanced R — Hadley Wickham  
- R Programming for Data Science — Roger D. Peng  
- Machine Learning: A Probabilistic Perspective — Kevin P. Murphy  
- Pattern Recognition — Sergios Theodoridis and Konstantinos Koutroumbas  
- Computer Photography — Marc Levoy  
- Digital Image Processing — Rafael C. Gonzalez and Richard E. Woods  
- Deep Learning — Ian Goodfellow, Yoshua Bengio, and Aaron Courville  
- Neural Networks and Learning Machines — Simon Haykin  
- Deep Learning — Yoshua Bengio  
- Deep Learning — Ian Goodfellow, Yoshua Bengio, and Aaron Courville  
- Reconciling Bayesian and Frequentist Statistics in the Era of Big Data — Joseph Romano and Azeem M. Shaikh  
- The Signal and the Noise: Why So Many Predictions Fail—but Some Don't — Nate Silver  
- Statistics Done Wrong — Alex Reinhart  
- Statistisches Modellieren — Wilhelm K. H. and Martina  
- Head First Statistics — Dawn Griffiths  
- Statistics in Plain English — Timothy C. Urdan  
- Statistics — Robert S. Witte and John S. Witte  
- Practical Statistics for Data Scientists — Peter Bruce and Andrew Bruce  
- Statistics for People Who (Think They) Hate Statistics — Neil J. Salkind  
- Stats: Data and Models — Richard D. De Veaux, Paul F. Velleman, and David E. Bock  
- Statistics — Robert S. Witte and John S. Witte  
- OpenIntro Statistics — David M. Diez, Christopher D. Barr, and Mine Cetinkaya‑Rundel  
- Seeing Statistics — Gary H. McClelland  
- Statistics — Robert S. Witte and John S. Witte  
- Statistics for Experimenters: Design, Innovation, and Discovery — George E. P. Box, J. Stuart Hunter, and William G. Hunter  
- Statistics — Robert S. Witte and John S. Witte  
- Discrete Mathematics with Applications — Susanna S. Epp  
- Discrete Mathematics — Richard Johnsonbaugh  
- Proofs from THE BOOK — Martin Aigner, Gunter  
- Concrete Mathematics: A Foundation for Computer Science — Ronald L. Graham, Donald E. Knuth, and Oren Patashnik  
- Discrete Mathematics and Its Applications — Kenneth H. Rosen  
- Discrete Mathematics — Richard Johnsonbaugh  
- Combinatorics: Topics, Techniques, Algorithms — Peter J. Cameron  
- Discrete Mathematics and Its Applications — Kenneth H. Rosen  
- Discrete Mathematics — Richard Johnsonbaugh  
- Introduction to Graph Theory — Douglas B. West  
- Discrete Mathematics and Its Applications — Kenneth H. Rosen  
- Discrete Mathematics — Richard Johnsonbaugh  
- Enumerative Combinatorics — Richard P. Stanley  
- Combinatorics — Peter J. Cameron  
- Discrete Mathematics and Its Applications — Kenneth H. Rosen  
- Discrete Mathematics — Richard Johnsonbaugh  
- Analytic Combinatorics — Philippe Flajolet and Robert Sedgewick  
- Discrete Mathematics and Its Applications — Kenneth H. Rosen  
- Discrete Mathematics — Richard Johnsonbaugh  
- Discrete Mathematics and Its Applications — Kenneth H. Rosen  
- Discrete Mathematics — Richard Johnsonbaugh  
- Discrete Mathematics and Its Applications — Kenneth H. Rosen  
- Discrete Mathematics — Richard Johnsonbaugh  
- Discrete Mathematics and Its Applications — Kenneth H. Rosen  
- Discrete Mathematics — Richard Johnsonbaugh  
- Discrete Mathematics and Its Applications — Kenneth H. Rosen  
- Discrete Mathematics — Richard Johnsonbaugh  
- Discrete Mathematics and Its Applications — Kenneth H. Rosen  
- Discrete Mathematics — Richard Johnsonbaugh  
- Discrete Mathematics and Its Applications — Kenneth H. Rosen  
- Discrete Mathematics — Richard Johnsonbaugh  
- Discrete Mathematics and Its Applications — Kenneth H. Rosen  
- Discrete Mathematics — Richard Johnsonbaugh  

---

# Review
Annual technology stack review for AI/ML or when evaluating alternative languages for data science and machine learning workloads