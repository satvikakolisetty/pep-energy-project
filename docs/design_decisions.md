# Solution Overview and Design Decisions

This document details the decisions made in the construction of this data pipeline. The goal was not simply to meet the assignment's requirements, but to build a solution that reflects the standards of a modern, production ready system, emphasizing scalability, fault-tolerance, and automation.

### Solution Snapshot

This solution implements an end-to-end serverless data pipeline. At a high level, the data flows as follows:

* **Ingestion:** An **EventBridge** schedule triggers a **Simulator Lambda** every five minutes to generate and upload raw JSON data to **S3**.
* **Processing & Storage:** The S3 upload event triggers a **Processor Lambda**. This function process the data, identifies anomalies, and stores the processed records in **DynamoDB**.
* **Alerting & Error Handling:** The Processor Lambda publishes alerts for any detected anomalies to **SNS**. If the processor fails, the event is safely captured in an **SQS Dead-Letter Queue**.
* **Data Access:** An **API Gateway** exposes endpoints from a **FastAPI Lambda**, allowing a local Python script to query the data from DynamoDB and generate visualizations.



### 1. Architectural Foundation: Serverless and Event-Driven

Choosing a fully serverless, event-driven design wasn’t incidental; as it sets the tone for how the system scales, how it’s operated, and how little day-to-day maintenance it requires.

* **Why Serverless?** The primary challenge of any data pipeline is handling variable load. A traditional, server-based approach would require provisioning for peak capacity, leading to significant cost and maintenance overhead for idle resources. A serverless design using AWS Lambda is inherently more efficient. It scales horizontally from zero to thousands of parallel executions automatically, ensuring that we only pay for compute resources when data is actively being processed. This makes the system both highly scalable and cost-effective.

* **Why Event-Driven?** The components are decoupled and react to events (e.g., a file landing in S3, a scheduled timer). This creates a more resilient and maintainable system than a procedural script. If one component fails, it doesn't necessarily bring down the entire pipeline, and individual components can be updated or replaced without affecting the others.

### 2. Infrastructure as Code: Terraform with a Remote State Backend

The entire cloud infrastructure is defined declaratively using Terraform. More importantly, the Terraform state is managed remotely using an S3 bucket with a DynamoDB table for state locking.

* **Why IaC?** Manually configuring cloud infrastructure via a console is brittle, error-prone, and not reproducible. Defining infrastructure in code is the only way to guarantee consistent, version-controlled, and automated deployments.

* **Why a Remote Backend?** This is a critical decision for any project that moves beyond a single developer's laptop. Storing the state file locally is not viable for CI/CD or team collaboration.
    * **The S3 bucket** provides a single, durable source of truth for the infrastructure's state.
    * **The DynamoDB table** provides state locking, which is essential to prevent dangerous race conditions where concurrent `terraform apply` runs could corrupt the state.

### 3. API Design: The Right Tool for the Job

For the API layer, I chose to combine API Gateway with a FastAPI application running on AWS Lambda.

* **API Gateway's Role:** A Lambda function on its own is not a web server. API Gateway is the purpose-built service for this role, handling critical concerns like request routing, traffic management, and security. It decouples the public-facing contract of the API from the backend implementation.

* **FastAPI's Role:** While a plain Lambda function could have been used to query DynamoDB, using a framework like FastAPI demonstrates a commitment to building a high-quality, maintainable service. It provides several immediate benefits:
    * **Automatic Data Validation:** Through Pydantic, it enforces data contracts, automatically validating requests and serializing responses.
    * **Dependency Injection:** FastAPI’s structure encourages cleaner, more testable code.
    * **Auto-Generated Documentation:** The interactive Swagger UI is not just a convenience; it's a professional feature that makes the API immediately usable by other developers.

### 4. The Extra Credit Features

I implemented all three extra credit features because, in a real-world scenario, they are not extra they are core requirements for a production-worthy system that handles critical data.

* **Automated Alerting (SNS):** A pipeline without monitoring is a liability that can lead to silent failures. In this project, monitoring goes beyond system health (like CPU usage) and extends to data quality itself. The SNS alerting system provides immediate, real-time feedback on the detection of anomalous data. This allows stakeholders to be proactively notified of potential data quality issues, enabling faster investigation and maintaining trust in the data.
* **Error Handling (DLQ):**  Data integrity is paramount. A production pipeline must guarantee that no data is ever lost, even when failures occur. The SQS Dead-Letter Queue serves as a critical safety net for the data processor. If a Lambda invocation fails after all retries (for instance, due to corrupted input data or a temporary downstream issue), the original event is not discarded. Instead, it is safely captured in the DLQ. This makes the pipeline auditable and fully recoverable. An engineer can inspect the failed message, diagnose the root cause, deploy a fix, and then re-process the message from the queue, ensuring no data loss.
* **CI/CD (GitHub Actions):** Manual deployments are a primary source of human error and are not scalable or repeatable. The implemented GitHub Actions workflow handles every step—installing dependencies, packaging the application code, and deploying the infrastructure via Terraform without manual intervention. This increases deployment velocity, reduces the risk of production errors, and provides a complete audit trail of all changes made to the system.

**Terraform files are located in `/terraform`, Lambda service code is under `/src` (e.g., `/src/lambda_processor`), and CI/CD workflows in `/.github/workflows` and the visualization script is located in `/visualization/`, with all generated charts saved to `/visualization/charts/`.**