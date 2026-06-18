---
id: DD-005
title: Fraud-detection-service v2 architecture with online feature store
status: Proposed
date: 2024-06-15
authors: [team-sigma]
services: [fraud-detection-service]
---

# Fraud-detection-service v2 architecture with online feature store

## Goal

The primary goal of this design document is to outline the architecture for the second version of the `fraud-detection-service`, which will incorporate an online feature store. This upgrade aims to enhance the real-time capabilities of fraud detection by providing immediate access to feature data, thereby improving the accuracy and efficiency of fraud scoring.

## Non-Goals

- This document does not cover the implementation details of the machine learning models themselves.
- It does not address changes to the existing offline feature extraction processes.
- It does not propose changes to the current deployment pipeline or CI/CD processes.

## Proposal

The proposed architecture for the `fraud-detection-service` v2 introduces an online feature store using Redis, which will serve as a high-performance, low-latency data store for real-time feature data. The architecture will continue to use Python for the service logic, ensuring compatibility with existing machine learning models.

### Key Components:

- **Feature Store (Redis):** Redis will be used to store and retrieve feature data in real-time. This will allow the fraud detection models to access the most up-to-date information.
- **Model Serving Layer:** The existing model serving layer will be adapted to integrate with the online feature store, enabling it to fetch features dynamically during inference.
- **Data Ingestion Pipeline:** Kafka will be used to stream transactional data into the feature store. This ensures that the feature data is continuously updated and reflective of the current state.

## API / Schema Changes

- **New Endpoints:**
  - `POST /api/v2/fraud/features` to update feature data in the store.
  - `GET /api/v2/fraud/features/{transaction_id}` to retrieve feature data for a specific transaction.

- **Schema Changes:**
  - Feature data will be stored in a key-value format within Redis, where keys are transaction IDs and values are serialized feature sets.

## Migration Plan

The migration to the new architecture will be phased to minimize disruption:

1. **Phase 1:** Deploy the Redis-based feature store alongside the existing system, ensuring it receives all updates.
2. **Phase 2:** Gradually redirect a percentage of fraud scoring requests to the new system to validate performance and accuracy.
3. **Phase 3:** Once validated, fully transition all fraud scoring requests to use the online feature store.

## Risks

- **Data Consistency:** Ensuring that the feature store is consistently updated with the latest data is critical to maintaining the accuracy of fraud detection.
- **Performance Overhead:** Introducing an additional layer for feature storage and retrieval may introduce latency if not properly optimized.

## Open Questions

- What are the specific performance metrics we need to track to ensure the feature store does not become a bottleneck?
- How will we handle potential failures in the data ingestion pipeline to ensure data consistency? 

This proposal sets the stage for a more responsive and accurate fraud detection system, leveraging real-time data to enhance decision-making capabilities.
