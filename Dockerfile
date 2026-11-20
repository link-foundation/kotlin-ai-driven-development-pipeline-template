FROM eclipse-temurin:21-jre-noble@sha256:b4f9d2a0bc273417cf5219b7b832bbf0493ed500b7b57d5001d9f83374659060
WORKDIR /app
COPY build/runtime/ ./
USER 65532:65532
ENTRYPOINT ["java", "-cp", "/app/*", "template.MainKt"]
