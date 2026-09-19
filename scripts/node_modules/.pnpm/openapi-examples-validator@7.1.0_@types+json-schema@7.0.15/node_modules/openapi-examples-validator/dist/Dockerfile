FROM node:20.20-alpine3.23

RUN npm install -g openapi-examples-validator@7.1.0

ENV NODE_OPTIONS="--unhandled-rejections=strict"
ENTRYPOINT ["openapi-examples-validator"]
CMD ["--help"]