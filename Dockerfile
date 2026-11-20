FROM eclipse-temurin:24-jre-noble@sha256:b416d02335e702b0403ff280de9475a3348e29382285969c9d4e17862ce632e7
WORKDIR /app
COPY build/runtime/ ./
USER 65532:65532
ENTRYPOINT ["java", "-cp", "/app/*", "template.MainKt"]
