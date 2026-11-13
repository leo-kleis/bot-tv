import { h, render, createPortal } from 'preact';
import { useState, useEffect, useReducer, useRef, useCallback, useMemo } from 'preact/hooks';
import { memo } from 'preact/compat';
import htm from 'htm';

const html = htm.bind(h);

export {
  h,
  html,
  render,
  createPortal,
  memo,
  useState,
  useEffect,
  useReducer,
  useRef,
  useCallback,
  useMemo,
};
