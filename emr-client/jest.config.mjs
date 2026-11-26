export default {
  testEnvironment: 'node',
  extensionsToTreatAsEsm: ['.jsx'],
  transform: {
    '^.+\\.jsx$': './tests/jsx-transformer.mjs',
  },
  moduleNameMapper: {
    '\\.css$': '<rootDir>/tests/style-mock.mjs',
  },
};
