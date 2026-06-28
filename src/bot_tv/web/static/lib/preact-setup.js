import { h, render } from 'preact';
import { useState, useEffect, useReducer, useRef, useCallback, useMemo } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

export { h, html, render, useState, useEffect, useReducer, useRef, useCallback, useMemo };
